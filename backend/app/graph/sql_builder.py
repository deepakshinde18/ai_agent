"""Pure query-building logic for the fill_slots graph node.

Security model (SQL-injection-safe by construction):
  - STRUCTURE is 100% developer-authored and never changes at request time:
    table/column names, joins, order/limit (config/insights/*.yaml), and the
    where_clause_template itself -- including which columns it references and
    how they're combined (AND/OR/parens) -- comes verbatim from the
    `insight_definitions` row. The user's request can never add, remove, or
    reorder a condition, only supply the bound-parameter value that slots
    into a placeholder (`:slot_name`) already present in that fixed template.
  - Column *names* the LLM is even allowed to talk about come only from the
    insight's own slot_definitions whitelist -- never invented, never taken
    from raw user text. RAG-sourced column_metadata is used only as prompt
    *context* (descriptions/synonyms) so the LLM recognizes a column from
    however the user phrased it.
  - VALUES (the actual numbers/strings the user typed) are never string-
    interpolated into SQL text -- they always travel as bound parameters.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.sql.elements import TextClause

from app.graph.state import Operator, ResolvedFilter
from app.llm import get_chat_model
from app.rag.column_matcher import get_column_context

CONFIG_INSIGHTS_DIR = Path(__file__).resolve().parents[2] / "config" / "insights"

SQL_OPERATORS: dict[Operator, str] = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "ILIKE",
    "in": "IN",
}


class SlotResolutionError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# Steps (a)+(b)+(c): one LLM call resolves a bound-parameter value for each
# of this insight's fixed slots -- grounded with each slot's real column name
# and RAG column-metadata description, so the LLM (not a brittle regex) does
# the natural-language normalization (e.g. "1 million" -> 1000000, "10k" ->
# 10000). Slots the user didn't address are left for render_where_clause to
# fall back to their configured default.
# ---------------------------------------------------------------------------


def _coerce_value(raw_value: str, expected_type: str) -> Any:
    if expected_type == "numeric":
        cleaned = raw_value.replace(",", "").replace("$", "").strip()
        try:
            return float(cleaned) if "." in cleaned else int(cleaned)
        except ValueError as exc:
            raise SlotResolutionError(f"Expected a numeric value, got '{raw_value}'") from exc
    if expected_type == "percentage":
        # LLM normalizes to a plain percentage number (see the resolve_slot_values
        # prompt) -- e.g. "10%" / "ten percent" -> "10". Stored as a 0-1 fraction
        # so it can be multiplied directly against another column in a
        # developer-authored template, e.g. "col >= (other_col * :pct_slot)".
        cleaned = raw_value.replace("%", "").replace(",", "").strip()
        try:
            return float(cleaned) / 100
        except ValueError as exc:
            raise SlotResolutionError(f"Expected a percentage value, got '{raw_value}'") from exc
    if expected_type == "numeric_list":
        # For slots whose configured operator is "in" (e.g. "rank IN
        # :rank"), the LLM normalizes to a comma-separated list of digits
        # (see the resolve_slot_values prompt) -- e.g. "1,2,3,4" or "ranks 1,
        # 2, 3 and 4" -> "1,2,3,4". Returned as an actual list so it can bind
        # to an expanding IN parameter.
        parts = [p.strip() for p in raw_value.split(",") if p.strip()]
        if not parts:
            raise SlotResolutionError(f"Expected a comma-separated list of numbers, got '{raw_value}'")
        try:
            return [float(p) if "." in p else int(p) for p in parts]
        except ValueError as exc:
            raise SlotResolutionError(f"Expected a comma-separated list of numbers, got '{raw_value}'") from exc
    return raw_value


class _SlotValue(BaseModel):
    slot_name: str = Field(description="The exact slot_name from the list provided -- never invent one")
    value: str = Field(
        description=(
            "The value for this slot, normalized to plain text: for numeric "
            "slots, digits only -- no words, commas, or currency symbols "
            "(e.g. 'one million' or '1 million' becomes '1000000', '10k' "
            "becomes '10000'); for percentage slots, the plain percentage "
            "number with no '%' sign or words (e.g. '10%' or 'ten percent' "
            "becomes '10'); for numeric_list slots, a comma-separated list "
            "of digits with no spaces or words (e.g. 'ranks 1, 2, 3 and 4' "
            "becomes '1,2,3,4')."
        )
    )


class _SlotValues(BaseModel):
    values: list[_SlotValue] = Field(default_factory=list)


def resolve_slot_values(raw_input: str, target_type: str, slot_definitions: dict) -> list[ResolvedFilter]:
    slots = slot_definitions.get("slots", [])
    if not slots:
        return []

    slot_lines = []
    for slot in slots:
        context = get_column_context(target_type, slot["column_name"]) or slot["column_name"]
        slot_lines.append(f"- slot_name={slot['slot_name']!r}: {context} (type={slot.get('expected_type', 'string')})")

    model = get_chat_model(temperature=0.0).with_structured_output(_SlotValues)
    result: _SlotValues = model.invoke(
        [
            {
                "role": "system",
                "content": (
                    "The user is querying a fixed report that has the filter slots "
                    "listed below. Decide which slots, if any, the user's request "
                    "supplies a value for -- include ONLY slots they actually "
                    "addressed, using the exact slot_name given. Normalize each "
                    "value yourself: numeric slots as plain digits (e.g. word-form "
                    "or shorthand numbers like '1 million' or '10k' become "
                    "'1000000' or '10000'); percentage slots as the plain "
                    "percentage number with no '%' sign or words (e.g. '10%' or "
                    "'more than 10 percent' becomes '10'); numeric_list slots as "
                    "a comma-separated list of digits with no spaces or words "
                    "(e.g. 'rank in 1, 2, 3 and 4' becomes "
                    "'1,2,3,4').\n\nSlots:\n" + "\n".join(slot_lines)
                ),
            },
            {"role": "user", "content": raw_input},
        ]
    )

    slot_by_name = {slot["slot_name"]: slot for slot in slots}
    resolved: list[ResolvedFilter] = []
    for item in result.values:
        slot = slot_by_name.get(item.slot_name)
        if slot is None:
            # LLM named a slot outside the whitelist -- drop it rather than
            # trust unvalidated output for anything SQL-shaped.
            continue
        value = _coerce_value(item.value, slot.get("expected_type", "string"))
        default_operator = (slot.get("default") or {}).get("operator", "eq")
        resolved.append(
            {
                "column_name": slot["column_name"],
                "operator": default_operator,
                "value": value,
                "param_name": slot["slot_name"],
            }
        )

    missing_required = [
        slot["slot_name"]
        for slot in slots
        if slot.get("required") and slot["slot_name"] not in {rf["param_name"] for rf in resolved}
    ]
    if missing_required:
        raise SlotResolutionError(f"Could not resolve required filter(s): {', '.join(missing_required)}")

    return resolved


# ---------------------------------------------------------------------------
# Step (d)+(e): fill in the fixed, developer-authored where_clause_template's
# bound-parameter values. The template's SQL text (columns, operators,
# AND/OR, parens) is never touched -- only sql_params changes per request.
# ---------------------------------------------------------------------------


def render_where_clause(
    where_clause_template: str,
    resolved_filters: list[ResolvedFilter],
    slot_definitions: dict,
) -> tuple[str, dict[str, Any], list[str]]:
    resolved_by_slot = {rf["param_name"]: rf for rf in resolved_filters}
    sql_params: dict[str, Any] = {}
    expanding_params: list[str] = []

    for slot in slot_definitions.get("slots", []):
        name = slot["slot_name"]
        rf = resolved_by_slot.get(name)
        if rf is not None:
            value, operator = rf["value"], rf["operator"]
        else:
            default = slot.get("default")
            if default is None:
                # The template's placeholder (:name) is unconditional, so every
                # slot it references must resolve to something -- either from
                # the user's request or a configured default.
                raise SlotResolutionError(
                    f"No value given and no default configured for slot '{name}'"
                )
            value, operator = default["value"], default["operator"]

        sql_params[name] = value
        if operator == "in":
            expanding_params.append(name)

    return where_clause_template, sql_params, expanding_params


# ---------------------------------------------------------------------------
# Step (d): load the trusted, developer-authored insight YAML
# ---------------------------------------------------------------------------


def load_insight_config(config_yaml_path: str) -> dict:
    path = CONFIG_INSIGHTS_DIR / config_yaml_path
    if not path.is_file():
        raise SlotResolutionError(f"Insight config not found: {config_yaml_path}")
    return yaml.safe_load(path.read_text())


# ---------------------------------------------------------------------------
# Step (f): assemble the final SQL. All structure here is trusted config.
# ---------------------------------------------------------------------------


def assemble_select_sql(from_table_name: str, where_clause: str, yaml_config: dict) -> str:
    select_parts = []
    for col in yaml_config["select_columns"]:
        column, alias = col["column"], col.get("alias", col["column"])
        select_parts.append(column if alias == column else f"{column} AS {alias}")
    select_clause = ", ".join(select_parts)

    sql = f"SELECT {select_clause} FROM {from_table_name}"
    for join in yaml_config.get("joins", []) or []:
        sql += f" {join['type']} JOIN {join['table']} ON {join['on']}"

    if where_clause:
        sql += f" WHERE {where_clause}"

    order_by = yaml_config.get("order_by") or []
    if order_by:
        order_clause = ", ".join(f"{o['column']} {o.get('direction', 'ASC')}" for o in order_by)
        sql += f" ORDER BY {order_clause}"

    limit = yaml_config.get("limit")
    if limit:
        sql += f" LIMIT {int(limit)}"

    return sql


def build_bound_statement(
    sql: str, sql_params: dict[str, Any], expanding_params: list[str]
) -> TextClause:
    stmt = text(sql)
    if expanding_params:
        stmt = stmt.bindparams(*(bindparam(name, expanding=True) for name in expanding_params))
    return stmt
