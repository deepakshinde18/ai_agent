from dataclasses import dataclass

from app.rag.chroma_client import get_intent_collection
from app.rag.embeddings import embed_query


@dataclass
class IntentCandidate:
    insight_type: str
    example_text: str
    confidence: float


@dataclass
class IntentMatchResult:
    top: IntentCandidate | None
    candidates: list[IntentCandidate]


def match_intent(text: str, n_results: int = 5) -> IntentMatchResult:
    collection = get_intent_collection()
    if collection.count() == 0:
        return IntentMatchResult(top=None, candidates=[])

    query_embedding = embed_query(text)
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
    )

    documents = result["documents"][0] if result["documents"] else []
    metadatas = result["metadatas"][0] if result["metadatas"] else []
    distances = result["distances"][0] if result["distances"] else []

    candidates = [
        IntentCandidate(
            insight_type=meta["insight_type"],
            example_text=doc,
            confidence=max(0.0, 1.0 - dist),
        )
        for doc, meta, dist in zip(documents, metadatas, distances, strict=True)
    ]

    top = candidates[0] if candidates else None
    return IntentMatchResult(top=top, candidates=candidates)
