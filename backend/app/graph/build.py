from typing import Literal

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from app.graph.nodes.clarify import clarify_node
from app.graph.nodes.error_handler import error_handler_node
from app.graph.nodes.fill_slots import fill_slots_node
from app.graph.nodes.intent_detect import detect_intent_node
from app.graph.nodes.intent_lookup import lookup_intent_node
from app.graph.nodes.narrative import generate_narrative_node
from app.graph.nodes.persist_interaction import persist_interaction_node
from app.graph.nodes.sanitize import sanitize_node
from app.graph.state import InsightAgentState


def _route_on_error(state: InsightAgentState) -> Literal["error", "ok"]:
    return "error" if state.get("error") else "ok"


def build_graph_definition() -> StateGraph:
    """Assembles the graph topology (no checkpointer yet -- see build_graph()).

    sanitize -> detect_intent -> (clarify | lookup_intent) -> fill_slots
             -> generate_narrative -> persist_interaction -> END

    Every fallible node can short-circuit to error_handler -> persist_interaction -> END.
    detect_intent's clarify/lookup_intent/error_handler branch is decided dynamically
    inside the node via Command(goto=...); the rest use static conditional edges
    since the branch is a simple error-vs-ok check.
    """
    graph = StateGraph(InsightAgentState)

    graph.add_node("sanitize", sanitize_node)
    graph.add_node("detect_intent", detect_intent_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("lookup_intent", lookup_intent_node)
    graph.add_node("fill_slots", fill_slots_node)
    graph.add_node("generate_narrative", generate_narrative_node)
    graph.add_node("error_handler", error_handler_node)
    graph.add_node("persist_interaction", persist_interaction_node)

    graph.set_entry_point("sanitize")

    graph.add_conditional_edges(
        "sanitize", _route_on_error, {"error": "error_handler", "ok": "detect_intent"}
    )
    # detect_intent routes itself via Command(goto=...) -- no add_conditional_edges needed.
    graph.add_edge("clarify", "persist_interaction")
    graph.add_conditional_edges(
        "lookup_intent", _route_on_error, {"error": "error_handler", "ok": "fill_slots"}
    )
    graph.add_conditional_edges(
        "fill_slots", _route_on_error, {"error": "error_handler", "ok": "generate_narrative"}
    )
    graph.add_conditional_edges(
        "generate_narrative",
        _route_on_error,
        {"error": "error_handler", "ok": "persist_interaction"},
    )
    graph.add_edge("error_handler", "persist_interaction")
    graph.add_edge("persist_interaction", END)

    return graph


def compile_graph(checkpointer: AsyncPostgresSaver):
    return build_graph_definition().compile(checkpointer=checkpointer)
