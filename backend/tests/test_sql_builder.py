import pytest

from app.graph import sql_builder
from app.graph.sql_builder import (
    SlotResolutionError,
    assemble_select_sql,
    generate_generic_where_template,
    render_where_clause,
    resolve_filters,
)
from app.rag.column_matcher import ColumnMatch

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


def test_generate_generic_where_template_renders_all_present_filters():
    template = generate_generic_where_template(["acct_bal", "city"])
    resolved = [
        {"column_name": "account_balance", "operator": "gt", "value": 1_000_000, "param_name": "acct_bal"},
        {"column_name": "city", "operator": "eq", "value": "xyz", "param_name": "city"},
    ]
    where, params, expanding = render_where_clause(template, resolved)
    assert where == "account_balance > :acct_bal AND city = :city"
    assert params == {"acct_bal": 1_000_000, "city": "xyz"}
    assert expanding == []


def test_render_where_clause_partial_filters_omits_missing_slot():
    template = generate_generic_where_template(["acct_bal", "city"])
    resolved = [{"column_name": "account_balance", "operator": "gt", "value": 5, "param_name": "acct_bal"}]
    where, params, _ = render_where_clause(template, resolved)
    assert where == "account_balance > :acct_bal"
    assert params == {"acct_bal": 5}


def test_render_where_clause_no_filters_is_empty():
    template = generate_generic_where_template(["acct_bal", "city"])
    where, params, _ = render_where_clause(template, [])
    assert where == ""
    assert params == {}


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


def test_resolve_filters_drops_column_not_in_slot_whitelist(monkeypatch):
    # Simulate RAG returning a column that was never declared for this
    # insight_type -- the whitelist cross-check must drop it, not trust RAG.
    monkeypatch.setattr(
        sql_builder,
        "match_column",
        lambda hint, target_type, n_results=3: ColumnMatch(
            column_name="ssn", table="clients", data_type="string", confidence=0.99
        ),
    )
    extracted = [{"column_hint": "social security number", "operator": "eq", "value": "123"}]
    resolved = resolve_filters(extracted, "clients", SLOT_DEFINITIONS, confidence_threshold=0.6)
    assert resolved == []


def test_resolve_filters_drops_disallowed_operator(monkeypatch):
    monkeypatch.setattr(
        sql_builder,
        "match_column",
        lambda hint, target_type, n_results=3: ColumnMatch(
            column_name="city", table="clients", data_type="string", confidence=0.9
        ),
    )
    # "gt" isn't in city's allowed_operators (["eq", "like"])
    extracted = [{"column_hint": "city", "operator": "gt", "value": "xyz"}]
    resolved = resolve_filters(extracted, "clients", SLOT_DEFINITIONS, confidence_threshold=0.6)
    assert resolved == []


def test_resolve_filters_below_confidence_threshold_dropped(monkeypatch):
    monkeypatch.setattr(
        sql_builder,
        "match_column",
        lambda hint, target_type, n_results=3: ColumnMatch(
            column_name="account_balance", table="clients", data_type="numeric", confidence=0.1
        ),
    )
    extracted = [{"column_hint": "balance", "operator": "gt", "value": "1000000"}]
    resolved = resolve_filters(extracted, "clients", SLOT_DEFINITIONS, confidence_threshold=0.6)
    assert resolved == []


def test_resolve_filters_missing_required_slot_raises(monkeypatch):
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
    monkeypatch.setattr(sql_builder, "match_column", lambda hint, target_type, n_results=3: None)
    with pytest.raises(SlotResolutionError):
        resolve_filters([], "clients", slots, confidence_threshold=0.6)


def test_resolve_filters_coerces_numeric_value(monkeypatch):
    monkeypatch.setattr(
        sql_builder,
        "match_column",
        lambda hint, target_type, n_results=3: ColumnMatch(
            column_name="account_balance", table="clients", data_type="numeric", confidence=0.9
        ),
    )
    extracted = [{"column_hint": "balance", "operator": "gt", "value": "1,000,000"}]
    resolved = resolve_filters(extracted, "clients", SLOT_DEFINITIONS, confidence_threshold=0.6)
    assert resolved == [
        {"column_name": "account_balance", "operator": "gt", "value": 1_000_000, "param_name": "acct_bal"}
    ]
