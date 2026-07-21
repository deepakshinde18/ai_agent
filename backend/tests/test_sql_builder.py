import pytest

from app.graph import sql_builder
from app.graph.sql_builder import (
    SlotResolutionError,
    assemble_select_sql,
    render_where_clause,
    resolve_slot_values,
)

SLOT_DEFINITIONS = {
    "slots": [
        {
            "slot_name": "acct_bal",
            "column_name": "account_balance",
            "expected_type": "numeric",
            "allowed_operators": ["gt", "gte", "lt", "lte", "eq"],
            "required": False,
        },
        {
            "slot_name": "city",
            "column_name": "city",
            "expected_type": "string",
            "allowed_operators": ["eq", "like"],
            "required": False,
        },
    ]
}

SLOT_DEFINITIONS_WITH_DEFAULTS = {
    "slots": [
        {
            "slot_name": "acct_bal",
            "column_name": "account_balance",
            "expected_type": "numeric",
            "allowed_operators": ["gt", "gte", "lt", "lte", "eq"],
            "required": False,
            "default": {"operator": "gte", "value": 10000},
        },
        {
            "slot_name": "city",
            "column_name": "city",
            "expected_type": "string",
            "allowed_operators": ["eq", "like"],
            "required": False,
            "default": {"operator": "eq", "value": "ny"},
        },
    ]
}

FIXED_TEMPLATE = "account_balance >= :acct_bal AND city = :city"

# brkg_sweep_cash is compared against a percentage of curr_asset -- the
# multiplication itself is fixed template SQL; only the percentage's bound
# value changes per request.
SWEEP_TEMPLATE = (
    "curr_asset >= :curr_asset AND brkg_sweep_cash >= (curr_asset * :brkg_sweep_pct)"
)

SLOT_DEFINITIONS_SWEEP_PCT = {
    "slots": [
        {
            "slot_name": "curr_asset",
            "column_name": "curr_asset",
            "expected_type": "numeric",
            "allowed_operators": ["gte"],
            "required": False,
            "default": {"operator": "gte", "value": 10000},
        },
        {
            "slot_name": "brkg_sweep_pct",
            "column_name": "brkg_sweep_cash",
            "expected_type": "percentage",
            "allowed_operators": ["gte"],
            "required": False,
            "default": {"operator": "gte", "value": 0.02},
        },
    ]
}

# Full original scenario: curr_asset >= 10000 AND brkg_sweep_cash >=
# (curr_asset * 0.02) AND brkg_sweep_cash_rank IN (1,2,3,4).
SWEEP_TEMPLATE_WITH_RANK = (
    "curr_asset >= :curr_asset AND brkg_sweep_cash >= (curr_asset * :brkg_sweep_pct) "
    "AND brkg_sweep_cash_rank IN :brkg_sweep_cash_rank"
)

SLOT_DEFINITIONS_SWEEP_PCT_AND_RANK = {
    "slots": [
        *SLOT_DEFINITIONS_SWEEP_PCT["slots"],
        {
            "slot_name": "brkg_sweep_cash_rank",
            "column_name": "brkg_sweep_cash_rank",
            "expected_type": "numeric_list",
            "allowed_operators": ["in"],
            "required": False,
            # operator is fixed config ("in") -- never chosen by the user,
            # only the list of values it binds against can change.
            "default": {"operator": "in", "value": [1, 2, 3, 4]},
        },
    ]
}


def test_render_where_clause_returns_template_unchanged():
    # Structure (columns, operators, AND/OR) is authored config -- render
    # must never rewrite it, only supply bound-parameter values.
    resolved = [
        {"column_name": "account_balance", "operator": "gt", "value": 1_000_000, "param_name": "acct_bal"},
        {"column_name": "city", "operator": "eq", "value": "sf", "param_name": "city"},
    ]
    where, params, expanding = render_where_clause(FIXED_TEMPLATE, resolved, SLOT_DEFINITIONS_WITH_DEFAULTS)
    assert where == FIXED_TEMPLATE
    assert params == {"acct_bal": 1_000_000, "city": "sf"}
    assert expanding == []


def test_render_where_clause_falls_back_to_slot_default_when_user_omits_it():
    # User only mentioned account balance -- city's placeholder still needs a
    # value, so it falls back to its configured default ('ny').
    resolved = [
        {"column_name": "account_balance", "operator": "gt", "value": 1_000_000, "param_name": "acct_bal"}
    ]
    where, params, _ = render_where_clause(FIXED_TEMPLATE, resolved, SLOT_DEFINITIONS_WITH_DEFAULTS)
    assert where == FIXED_TEMPLATE
    assert params == {"acct_bal": 1_000_000, "city": "ny"}


def test_render_where_clause_all_defaults_when_user_gives_no_filters():
    where, params, _ = render_where_clause(FIXED_TEMPLATE, [], SLOT_DEFINITIONS_WITH_DEFAULTS)
    assert where == FIXED_TEMPLATE
    assert params == {"acct_bal": 10000, "city": "ny"}


def test_render_where_clause_user_value_overrides_default():
    resolved = [{"column_name": "city", "operator": "eq", "value": "sf", "param_name": "city"}]
    where, params, _ = render_where_clause(FIXED_TEMPLATE, resolved, SLOT_DEFINITIONS_WITH_DEFAULTS)
    assert where == FIXED_TEMPLATE
    assert params == {"acct_bal": 10000, "city": "sf"}


def test_render_where_clause_raises_when_slot_has_no_value_or_default():
    # SLOT_DEFINITIONS (no defaults) + no resolved filters means the
    # template's placeholders can't all be filled -- that's a config error,
    # not a silently-dropped clause.
    with pytest.raises(SlotResolutionError):
        render_where_clause(FIXED_TEMPLATE, [], SLOT_DEFINITIONS)


def test_assemble_select_sql_includes_where_order_and_limit():
    cfg = {
        "select_columns": [{"column": "client_id", "alias": "id"}, {"column": "city"}],
        "joins": [],
        "order_by": [{"column": "client_id", "direction": "ASC"}],
        "limit": 50,
    }
    sql = assemble_select_sql("clients", "city = :city", cfg)
    assert sql == (
        "SELECT client_id AS id, city FROM clients WHERE city = :city "
        "ORDER BY client_id ASC LIMIT 50"
    )


def test_assemble_select_sql_omits_where_when_empty():
    cfg = {"select_columns": [{"column": "client_id"}]}
    sql = assemble_select_sql("clients", "", cfg)
    assert "WHERE" not in sql


class _FakeStructuredModel:
    def __init__(self, result: "sql_builder._SlotValues"):
        self._result = result

    def invoke(self, messages):
        return self._result


class _FakeChatModel:
    def __init__(self, result: "sql_builder._SlotValues"):
        self._result = result

    def with_structured_output(self, schema):
        return _FakeStructuredModel(self._result)


def _mock_llm(monkeypatch, values: list[tuple[str, str]]):
    """Stub out the LLM call resolve_slot_values makes, and the RAG lookup
    used only for prompt context (irrelevant to what's asserted here)."""
    result = sql_builder._SlotValues(
        values=[sql_builder._SlotValue(slot_name=name, value=value) for name, value in values]
    )
    monkeypatch.setattr(sql_builder, "get_column_context", lambda table, column_name: None)
    monkeypatch.setattr(sql_builder, "get_chat_model", lambda temperature=0.0: _FakeChatModel(result))


def test_resolve_slot_values_normalizes_llm_output_into_resolved_filter(monkeypatch):
    # The LLM is expected to normalize "1 million" itself -- resolve_slot_values
    # just needs to trust and coerce the digits it comes back with.
    _mock_llm(monkeypatch, [("acct_bal", "1000000")])
    resolved = resolve_slot_values(
        "clients with account balance greater than 1 million", "clients", SLOT_DEFINITIONS_WITH_DEFAULTS
    )
    assert resolved == [
        {"column_name": "account_balance", "operator": "gte", "value": 1_000_000, "param_name": "acct_bal"}
    ]


def test_resolve_slot_values_drops_slot_name_outside_whitelist(monkeypatch):
    # Simulate the LLM naming a slot that was never declared for this
    # insight_type -- must be dropped, not trusted for SQL.
    _mock_llm(monkeypatch, [("ssn", "123")])
    resolved = resolve_slot_values("ssn is 123", "clients", SLOT_DEFINITIONS_WITH_DEFAULTS)
    assert resolved == []


def test_resolve_slot_values_missing_required_slot_raises(monkeypatch):
    slots = {
        "slots": [
            {
                "slot_name": "acct_bal",
                "column_name": "account_balance",
                "expected_type": "numeric",
                "allowed_operators": ["gt"],
                "required": True,
            }
        ]
    }
    _mock_llm(monkeypatch, [])
    with pytest.raises(SlotResolutionError):
        resolve_slot_values("hello", "clients", slots)


def test_resolve_slot_values_raises_on_non_numeric_value(monkeypatch):
    _mock_llm(monkeypatch, [("acct_bal", "a lot")])
    with pytest.raises(SlotResolutionError):
        resolve_slot_values("balance is a lot", "clients", SLOT_DEFINITIONS_WITH_DEFAULTS)


def test_resolve_slot_values_coerces_currency_symbol_and_commas(monkeypatch):
    _mock_llm(monkeypatch, [("acct_bal", "$1,000,000")])
    resolved = resolve_slot_values("balance over $1,000,000", "clients", SLOT_DEFINITIONS_WITH_DEFAULTS)
    assert resolved == [
        {"column_name": "account_balance", "operator": "gte", "value": 1_000_000, "param_name": "acct_bal"}
    ]


def test_resolve_slot_values_coerces_percentage_to_fraction(monkeypatch):
    # User says "10%" -- LLM normalizes to the plain number "10", and
    # _coerce_value turns that into the 0.10 fraction the template's
    # "curr_asset * :brkg_sweep_pct" multiplication expects.
    _mock_llm(monkeypatch, [("brkg_sweep_pct", "10")])
    resolved = resolve_slot_values(
        "brokerage sweep cash more than 10% of curr asset", "accounts", SLOT_DEFINITIONS_SWEEP_PCT
    )
    assert resolved == [
        {"column_name": "brkg_sweep_cash", "operator": "gte", "value": 0.10, "param_name": "brkg_sweep_pct"}
    ]


def test_resolve_slot_values_raises_on_non_numeric_percentage(monkeypatch):
    _mock_llm(monkeypatch, [("brkg_sweep_pct", "a lot")])
    with pytest.raises(SlotResolutionError):
        resolve_slot_values("sweep cash is a lot of curr asset", "accounts", SLOT_DEFINITIONS_SWEEP_PCT)


def test_render_where_clause_keeps_percentage_formula_template_unchanged():
    # Structure -- including the "(curr_asset * :brkg_sweep_pct)" formula --
    # is fixed config; only the bound percentage value changes per request.
    resolved = [
        {"column_name": "brkg_sweep_cash", "operator": "gte", "value": 0.10, "param_name": "brkg_sweep_pct"}
    ]
    where, params, expanding = render_where_clause(SWEEP_TEMPLATE, resolved, SLOT_DEFINITIONS_SWEEP_PCT)
    assert where == SWEEP_TEMPLATE
    assert params == {"curr_asset": 10000, "brkg_sweep_pct": 0.10}
    assert expanding == []


def test_render_where_clause_falls_back_to_default_percentage():
    where, params, _ = render_where_clause(SWEEP_TEMPLATE, [], SLOT_DEFINITIONS_SWEEP_PCT)
    assert where == SWEEP_TEMPLATE
    assert params == {"curr_asset": 10000, "brkg_sweep_pct": 0.02}


def test_resolve_slot_values_coerces_comma_list_into_int_list(monkeypatch):
    # "rank in 1,2,3,4" -- LLM normalizes to the digit-only comma string
    # "1,2,3,4", and _coerce_value turns that into an actual [1, 2, 3, 4]
    # list ready to bind to an expanding IN parameter.
    _mock_llm(monkeypatch, [("brkg_sweep_cash_rank", "1,2,3,4")])
    resolved = resolve_slot_values(
        "brokerage cash sweep rank in 1,2,3,4", "accounts", SLOT_DEFINITIONS_SWEEP_PCT_AND_RANK
    )
    assert resolved == [
        {
            "column_name": "brkg_sweep_cash_rank",
            "operator": "in",
            "value": [1, 2, 3, 4],
            "param_name": "brkg_sweep_cash_rank",
        }
    ]


def test_resolve_slot_values_raises_on_empty_list(monkeypatch):
    _mock_llm(monkeypatch, [("brkg_sweep_cash_rank", "")])
    with pytest.raises(SlotResolutionError):
        resolve_slot_values("rank is nothing", "accounts", SLOT_DEFINITIONS_SWEEP_PCT_AND_RANK)


def test_render_where_clause_marks_numeric_list_slot_as_expanding_param():
    resolved = [
        {
            "column_name": "brkg_sweep_cash_rank",
            "operator": "in",
            "value": [1, 2, 3, 4],
            "param_name": "brkg_sweep_cash_rank",
        }
    ]
    where, params, expanding = render_where_clause(
        SWEEP_TEMPLATE_WITH_RANK, resolved, SLOT_DEFINITIONS_SWEEP_PCT_AND_RANK
    )
    assert where == SWEEP_TEMPLATE_WITH_RANK
    assert params == {"curr_asset": 10000, "brkg_sweep_pct": 0.02, "brkg_sweep_cash_rank": [1, 2, 3, 4]}
    assert expanding == ["brkg_sweep_cash_rank"]


def test_render_where_clause_falls_back_to_default_rank_list():
    where, params, expanding = render_where_clause(
        SWEEP_TEMPLATE_WITH_RANK, [], SLOT_DEFINITIONS_SWEEP_PCT_AND_RANK
    )
    assert where == SWEEP_TEMPLATE_WITH_RANK
    assert params == {"curr_asset": 10000, "brkg_sweep_pct": 0.02, "brkg_sweep_cash_rank": [1, 2, 3, 4]}
    assert expanding == ["brkg_sweep_cash_rank"]
