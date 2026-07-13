from typing import Any, Literal, TypedDict

Operator = Literal["eq", "ne", "gt", "gte", "lt", "lte", "like", "in"]

ErrorCode = Literal[
    "PII_BLOCKED",
    "INJECTION_DETECTED",
    "INTENT_NOT_FOUND",
    "SLOT_RESOLUTION_FAILED",
    "SQL_EXECUTION_FAILED",
    "NARRATIVE_FAILED",
    "UNKNOWN",
]


class ErrorInfo(TypedDict):
    node: str
    code: ErrorCode
    user_message: str
    internal_detail: str


class FilterCondition(TypedDict):
    column_hint: str
    operator: Operator
    value: Any


class ResolvedFilter(TypedDict):
    column_name: str
    operator: Operator
    value: Any
    param_name: str


class InsightAgentState(TypedDict, total=False):
    # identity / session
    session_id: str
    user_id: str
    raw_input: str

    # sanitize
    sanitized_input: str
    pii_entities: list[dict]
    injection_flag: bool

    # intent
    intent_candidates: list[dict]
    resolved_intent: str | None
    intent_confidence: float

    # lookup
    target_type: str | None
    from_table_name: str | None
    where_clause_template: str | None
    slot_definitions: dict | None
    config_yaml_path: str | None

    # slot filling
    extracted_filters: list[FilterCondition]
    resolved_filters: list[ResolvedFilter]
    rendered_where_clause: str | None
    final_sql: str | None
    sql_params: dict[str, Any]

    # execution
    fetched_rows: list[dict]
    row_count: int

    # narrative
    narrative_complete: str | None

    # control / error
    error: ErrorInfo | None
    needs_clarification: bool
    clarification_message: str | None

    # timing (set at entry, used by persist_interaction)
    started_at_ms: float
