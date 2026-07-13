"""Pure query-building logic for the fill_slots graph node.

Security model (SQL-injection-safe by construction):
  - STRUCTURE (table names, column names, join clauses, order/limit) always
    comes from developer-authored config (Postgres `insight_definitions` row
    + config/insights/*.yaml) or from a column name that has been resolved
    via RAG *and* cross-checked against that config's slot whitelist. Never
    from raw user text or unvalidated LLM output.
  - VALUES (the actual numbers/strings the user typed) are never string-
    interpolated into SQL text -- they always travel as bound parameters.
"""

from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.sql.elements import TextClause

from app.graph.state import FilterCondition, Operator, ResolvedFilter
from app.llm import get_chat_model
from app.rag.column_matcher import match_column

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

_ALLOWED_OPERATORS = tuple(SQL_OPERATORS.keys())
_jinja_env = Environment(autoescape=False)


class SlotResolutionError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# Step (a): LLM extracts {column_hint, operator, value} filters from raw text
# ---------------------------------------------------------------------------


class _ExtractedFilter(BaseModel):
    column_hint: str = Field(description="The phrase the user used to refer to a column, e.g. 'account balance'")
    operator: str = Field(description=f"One of: {', '.join(_ALLOWED_OPERATORS)}")
    value: str = Field(description="The literal value as text, e.g. '1000000' or 'xyz'")


class _ExtractedFilters(BaseModel):
    filters: list[_ExtractedFilter] = Field(default_factory=list)


def extract_filters(raw_input: str) -> list[FilterCondition]:
    model = get_chat_model(temperature=0.0).with_structured_output(_ExtractedFilters)
    result: _ExtractedFilters = model.invoke(
        [
            {
                "role": "system",
                "content": (
                    "Extract filter conditions from the user's data-query request. "
                    f"operator must be exactly one of: {', '.join(_ALLOWED_OPERATORS)}. "
                    "If the user gives no filters, return an empty list."
                ),
            },
            {"role": "user", "content": raw_input},
        ]
    )
    filters: list[FilterCondition] = []
    for f in result.filters:
        op = f.operator.lower().strip()
        if op not in _ALLOWED_OPERATORS:
            continue
        filters.append({"column_hint": f.column_hint, "operator": op, "value": f.value})  # type: ignore[typeddict-item]
    return filters


# ---------------------------------------------------------------------------
# Steps (b)+(c): RAG-resolve column_hint -> real column, whitelist cross-check
# ---------------------------------------------------------------------------


def _coerce_value(raw_value: str, expected_type: str) -> Any:
    if expected_type == "numeric":
        cleaned = raw_value.replace(",", "").strip()
        try:
            return float(cleaned) if "." in cleaned else int(cleaned)
        except ValueError as exc:
            raise SlotResolutionError(f"Expected a numeric value, got '{raw_value}'") from exc
    return raw_value


def resolve_filters(
    extracted: list[FilterCondition],
    target_type: str,
    slot_definitions: dict,
    confidence_threshold: float,
) -> list[ResolvedFilter]:
    slots = slot_definitions.get("slots", [])
    # Whitelist: only columns explicitly declared for this insight_type may
    # ever be interpolated into SQL, regardless of what RAG returns.
    slot_by_column = {slot["column_name"]: slot for slot in slots}

    resolved: list[ResolvedFilter] = []
    matched_slot_names: set[str] = set()

    for filt in extracted:
        match = match_column(filt["column_hint"], target_type)
        if match is None or match.confidence < confidence_threshold:
            continue
        slot = slot_by_column.get(match.column_name)
        if slot is None:
            # RAG matched a column that isn't whitelisted for this insight --
            # drop it rather than trust a probabilistic match for SQL structure.
            continue
        if filt["operator"] not in slot["allowed_operators"]:
            continue

        value = _coerce_value(str(filt["value"]), slot.get("expected_type", "string"))
        resolved.append(
            {
                "column_name": slot["column_name"],
                "operator": filt["operator"],  # type: ignore[typeddict-item]
                "value": value,
                "param_name": slot["slot_name"],
            }
        )
        matched_slot_names.add(slot["slot_name"])

    missing_required = [
        slot["slot_name"]
        for slot in slots
        if slot.get("required") and slot["slot_name"] not in matched_slot_names
    ]
    if missing_required:
        raise SlotResolutionError(
            f"Could not resolve required filter(s): {', '.join(missing_required)}"
        )

    return resolved


# ---------------------------------------------------------------------------
# Step (d)+(e): render the where_clause_template, collect bound params
# ---------------------------------------------------------------------------


def render_where_clause(
    where_clause_template: str, resolved_filters: list[ResolvedFilter]
) -> tuple[str, dict[str, Any], list[str]]:
    context: dict[str, Any] = {}
    sql_params: dict[str, Any] = {}
    expanding_params: list[str] = []

    for rf in resolved_filters:
        sql_op = SQL_OPERATORS[rf["operator"]]
        clause = f"{rf['column_name']} {sql_op} :{rf['param_name']}"
        context[f"{rf['param_name']}_clause"] = clause
        sql_params[rf["param_name"]] = rf["value"]
        if rf["operator"] == "in":
            expanding_params.append(rf["param_name"])

    rendered = _jinja_env.from_string(where_clause_template).render(**context).strip()
    return rendered, sql_params, expanding_params


def generate_generic_where_template(slot_names: list[str]) -> str:
    """Build a where_clause_template that ANDs together whichever slot
    clauses ended up resolved, in slot-definition order, skipping any that
    weren't present in the user's request. Used when seeding
    insight_definitions rows -- one generic shape works for any slot set.
    """
    lines = ["{%- set parts = [] -%}"]
    for name in slot_names:
        lines.append(f"{{%- if {name}_clause %}}{{% set _ = parts.append({name}_clause) %}}{{% endif -%}}")
    lines.append("{{ parts | join(' AND ') }}")
    return "\n".join(lines)


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
