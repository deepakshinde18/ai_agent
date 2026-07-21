from app.graph.state import ErrorInfo, InsightAgentState
from app.security_layer.injection_classifier import classify_injection
from app.security_layer.injection_heuristics import scan_for_injection
from app.security_layer.pii import scan_and_redact


async def sanitize_node(state: InsightAgentState) -> dict:
    raw_input = state["raw_input"]
    try:
        pii_result = scan_and_redact(raw_input)

        if pii_result.high_risk_detected:
            error: ErrorInfo = {
                "node": "sanitize",
                "code": "PII_BLOCKED",
                "user_message": (
                    "Your request appears to contain sensitive personal information "
                    "(e.g. SSN, credit card, bank account number) that can't be "
                    "processed. Please rephrase without it."
                ),
                "internal_detail": f"high_risk_entities={pii_result.high_risk_entity_types}",
            }
            return {"error": error, "pii_entities": pii_result.entities}

        # Heuristics first (cheap); only call the LLM classifier if they're clean.
        heuristic_hits = scan_for_injection(raw_input)
        injection_flag = bool(heuristic_hits)
        classifier_reason = None
        if not injection_flag:
            classification = classify_injection(pii_result.sanitized_text)
            injection_flag = classification.is_injection
            classifier_reason = classification.reason

        if injection_flag:
            error = {
                "node": "sanitize",
                "code": "INJECTION_DETECTED",
                "user_message": "Your request could not be processed for security reasons.",
                "internal_detail": f"heuristic_hits={heuristic_hits}, classifier_reason={classifier_reason}",
            }
            return {"error": error, "injection_flag": True, "pii_entities": pii_result.entities}

        return {
            "error": None,
            "sanitized_input": pii_result.sanitized_text,
            "pii_entities": pii_result.entities,
            "injection_flag": False,
        }
    except Exception as exc:  # noqa: BLE001 -- any failure here must route to error_handler, not crash the graph
        error = {
            "node": "sanitize",
            "code": "UNKNOWN",
            "user_message": "Something went wrong while processing your request.",
            "internal_detail": repr(exc),
        }
        return {"error": error}


if __name__ == "__main__":
    import asyncio

    sample_state = {"raw_input": "Show me clients with balance over 1 million in Springfield"}
    print(asyncio.run(sanitize_node(sample_state)))
