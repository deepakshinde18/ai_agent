from unittest.mock import patch

import pytest

from app.graph.build import _route_on_error
from app.graph.nodes import intent_detect
from app.graph.nodes.clarify import clarify_node
from app.graph.nodes.error_handler import error_handler_node
from app.rag.intent_matcher import IntentCandidate, IntentMatchResult


def test_route_on_error_ok_when_no_error():
    assert _route_on_error({}) == "ok"


def test_route_on_error_error_when_present():
    assert _route_on_error({"error": {"code": "UNKNOWN"}}) == "error"


async def test_clarify_node_lists_candidate_insight_types():
    state = {
        "intent_candidates": [
            {"insight_type": "clients_by_balance_city", "example_text": "x", "confidence": 0.5},
            {"insight_type": "other_insight", "example_text": "y", "confidence": 0.4},
        ]
    }
    result = await clarify_node(state)
    assert "clients_by_balance_city" in result["clarification_message"]
    assert "other_insight" in result["clarification_message"]


async def test_clarify_node_handles_no_candidates():
    result = await clarify_node({"intent_candidates": []})
    assert "rephrase" in result["clarification_message"]


async def test_error_handler_node_is_a_passthrough():
    state = {"error": {"node": "x", "code": "UNKNOWN", "user_message": "oops", "internal_detail": "boom"}}
    assert await error_handler_node(state) == {}


@pytest.mark.parametrize(
    ("confidence", "expected_goto"),
    [(0.95, "lookup_intent"), (0.1, "clarify")],
)
async def test_detect_intent_node_routes_on_confidence(confidence, expected_goto):
    fake_result = IntentMatchResult(
        top=IntentCandidate(insight_type="clients_by_balance_city", example_text="x", confidence=confidence),
        candidates=[IntentCandidate(insight_type="clients_by_balance_city", example_text="x", confidence=confidence)],
    )
    with patch.object(intent_detect, "match_intent", return_value=fake_result):
        command = await intent_detect.detect_intent_node({"sanitized_input": "clients in city xyz"})
    assert command.goto == expected_goto


async def test_detect_intent_node_routes_to_error_handler_when_no_match():
    with patch.object(intent_detect, "match_intent", return_value=IntentMatchResult(top=None, candidates=[])):
        command = await intent_detect.detect_intent_node({"sanitized_input": "asdkjaslkdj"})
    assert command.goto == "error_handler"
    assert command.update["error"]["code"] == "INTENT_NOT_FOUND"
