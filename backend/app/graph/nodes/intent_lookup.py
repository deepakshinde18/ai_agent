from sqlalchemy import select

from app.db.models import InsightDefinition
from app.db.session import AgentSessionLocal
from app.graph.state import ErrorInfo, InsightAgentState


async def lookup_intent_node(state: InsightAgentState) -> dict:
    try:
        async with AgentSessionLocal() as session:
            row = await session.scalar(
                select(InsightDefinition).where(
                    InsightDefinition.insight_type == state["resolved_intent"],
                    InsightDefinition.is_active.is_(True),
                )
            )

        if row is None:
            error: ErrorInfo = {
                "node": "lookup_intent",
                "code": "INTENT_NOT_FOUND",
                "user_message": "We don't have a configured report for that request yet.",
                "internal_detail": f"no insight_definitions row for insight_type={state.get('resolved_intent')!r}",
            }
            return {"error": error}

        return {
            "target_type": row.target_type,
            "from_table_name": row.from_table_name,
            "where_clause_template": row.where_clause_template,
            "slot_definitions": row.slot_definitions,
            "config_yaml_path": row.config_yaml_path,
        }
    except Exception as exc:  # noqa: BLE001
        error = {
            "node": "lookup_intent",
            "code": "UNKNOWN",
            "user_message": "Something went wrong while looking up that report definition.",
            "internal_detail": repr(exc),
        }
        return {"error": error}
