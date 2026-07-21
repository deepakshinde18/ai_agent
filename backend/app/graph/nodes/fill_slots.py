from app.db.target_session import target_engine
from app.graph.sql_builder import (
    SlotResolutionError,
    assemble_select_sql,
    build_bound_statement,
    load_insight_config,
    render_where_clause,
    resolve_slot_values,
)
from app.graph.state import ErrorInfo, InsightAgentState
from app.logging_conf import get_logger

logger = get_logger(__name__)


async def fill_slots_node(state: InsightAgentState) -> dict:
    try:
        resolved = resolve_slot_values(
            state["raw_input"], state["target_type"], state["slot_definitions"]
        )
        where_clause, sql_params, expanding_params = render_where_clause(
            state["where_clause_template"], resolved, state["slot_definitions"]
        )
        yaml_config = load_insight_config(state["config_yaml_path"])
        sql = assemble_select_sql(state["from_table_name"], where_clause, yaml_config)

        logger.info(
            "fill_slots_built_sql",
            session_id=state.get("session_id"),
            sql=sql,
            sql_params=sql_params,
        )

        stmt = build_bound_statement(sql, sql_params, expanding_params)
        async with target_engine.connect() as conn:
            result = await conn.execute(stmt, sql_params)
            rows = [dict(row._mapping) for row in result]

        return {
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
