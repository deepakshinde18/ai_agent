from app.config import get_settings
from app.db.target_session import target_engine
from app.graph.sql_builder import (
    SlotResolutionError,
    assemble_select_sql,
    build_bound_statement,
    extract_filters,
    load_insight_config,
    render_where_clause,
    resolve_filters,
)
from app.graph.state import ErrorInfo, InsightAgentState


async def fill_slots_node(state: InsightAgentState) -> dict:
    settings = get_settings()
    try:
        extracted = extract_filters(state["raw_input"])
        resolved = resolve_filters(
            extracted,
            state["target_type"],
            state["slot_definitions"],
            settings.column_match_confidence_threshold,
        )
        where_clause, sql_params, expanding_params = render_where_clause(
            state["where_clause_template"], resolved
        )
        yaml_config = load_insight_config(state["config_yaml_path"])
        sql = assemble_select_sql(state["from_table_name"], where_clause, yaml_config)
        stmt = build_bound_statement(sql, sql_params, expanding_params)

        async with target_engine.connect() as conn:
            result = await conn.execute(stmt, sql_params)
            rows = [dict(row._mapping) for row in result]

        return {
            "extracted_filters": extracted,
            "resolved_filters": resolved,
            "rendered_where_clause": where_clause,
            "final_sql": sql,
            "sql_params": sql_params,
            "fetched_rows": rows,
            "row_count": len(rows),
        }
    except SlotResolutionError as exc:
        error: ErrorInfo = {
            "node": "fill_slots",
            "code": "SLOT_RESOLUTION_FAILED",
            "user_message": f"Couldn't fully understand the filters in your request: {exc.message}",
            "internal_detail": repr(exc),
        }
        return {"error": error}
    except Exception as exc:  # noqa: BLE001
        error = {
            "node": "fill_slots",
            "code": "SQL_EXECUTION_FAILED",
            "user_message": "Something went wrong while fetching the data for your request.",
            "internal_detail": repr(exc),
        }
        return {"error": error}
