from app.graph.state import ErrorInfo, InsightAgentState
from seed.seed_insight_definitions import INSIGHT_DEFINITIONS

# Looked up in-process for now instead of querying insight_definitions in
# Postgres -- avoids needing that table seeded/migrated while the target DB
# setup is still in flux. Swap back to the DB-backed lookup once we're ready
# to persist these.
_DEFINITIONS_BY_TYPE = {d["insight_type"]: d for d in INSIGHT_DEFINITIONS}


async def lookup_intent_node(state: InsightAgentState) -> dict:
    try:
        definition = _DEFINITIONS_BY_TYPE.get(state["resolved_intent"])

        if definition is None:
            error: ErrorInfo = {
                "node": "lookup_intent",
                "code": "INTENT_NOT_FOUND",
                "user_message": "We don't have a configured report for that request yet.",
                "internal_detail": f"no INSIGHT_DEFINITIONS entry for insight_type={state.get('resolved_intent')!r}",
            }
            return {"error": error}

        return {
            "target_type": definition["target_type"],
            "from_table_name": definition["from_table_name"],
            "where_clause_template": definition["where_clause_template"],
            "slot_definitions": definition["slot_definitions"],
            "config_yaml_path": definition["config_yaml_path"],
        }
    except Exception as exc:  # noqa: BLE001
        error = {
            "node": "lookup_intent",
            "code": "UNKNOWN",
            "user_message": "Something went wrong while looking up that report definition.",
            "internal_detail": repr(exc),
        }
        return {"error": error}
