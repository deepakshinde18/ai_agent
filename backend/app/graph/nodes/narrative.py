from app.graph.sql_builder import load_insight_config
from app.graph.state import ErrorInfo, InsightAgentState
from app.narrative_adapter import stub_azure_impl as narrative_service


async def generate_narrative_node(state: InsightAgentState) -> dict:
    try:
        narrative_hints = None
        if state.get("config_yaml_path"):
            narrative_hints = load_insight_config(state["config_yaml_path"]).get("narrative_hints")

        chunks: list[str] = []
        async for chunk in narrative_service.generate(
            target_type=state.get("target_type", ""),
            insight_type=state.get("resolved_intent", ""),
            question=state["raw_input"],
            data=state.get("fetched_rows", []),
            narrative_hints=narrative_hints,
        ):
            chunks.append(chunk)

        return {"narrative_complete": "".join(chunks)}
    except Exception as exc:  # noqa: BLE001
        error: ErrorInfo = {
            "node": "generate_narrative",
            "code": "NARRATIVE_FAILED",
            "user_message": "We fetched your data but couldn't generate a narrative summary.",
            "internal_detail": repr(exc),
        }
        return {"error": error}


if __name__ == "__main__":
    import asyncio

    sample_state = {
        "raw_input": "clients with balance over 1 million in Springfield",
        "target_type": "clients",
        "resolved_intent": "clients_by_balance_city",
        "config_yaml_path": "clients_by_balance_city.yaml",
        "fetched_rows": [{"id": 1, "name": "Ava Thompson", "balance": 1_250_000, "city": "Springfield"}],
    }
    print(asyncio.run(generate_narrative_node(sample_state)))
