from dataclasses import dataclass, field
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

from app.config import get_settings


@dataclass
class PiiScanResult:
    sanitized_text: str
    entities: list[dict] = field(default_factory=list)  # for audit: [{entity_type, score}]
    high_risk_detected: bool = False
    high_risk_entity_types: list[str] = field(default_factory=list)


@lru_cache
def _get_analyzer() -> AnalyzerEngine:
    settings = get_settings()
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": settings.presidio_spacy_model}],
        }
    )
    return AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])


@lru_cache
def _get_anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()


def scan_and_redact(text: str) -> PiiScanResult:
    """Scan for PII and redact low-risk entities in place.

    Policy (confirmed): redact low-risk entities (e.g. PERSON, LOCATION --
    legitimate in queries like "accounts for John Smith") and continue;
    flag high_risk_detected for entities in settings.presidio_high_risk_entities
    (SSN, credit card, etc.) so the calling node can hard-block instead.
    """
    settings = get_settings()
    analyzer_results = _get_analyzer().analyze(text=text, language="en")

    high_risk_types = [
        r.entity_type for r in analyzer_results if r.entity_type in settings.presidio_high_risk_entities
    ]

    anonymized = _get_anonymizer().anonymize(text=text, analyzer_results=analyzer_results)

    return PiiScanResult(
        sanitized_text=anonymized.text,
        entities=[{"entity_type": r.entity_type, "score": r.score} for r in analyzer_results],
        high_risk_detected=bool(high_risk_types),
        high_risk_entity_types=high_risk_types,
    )
