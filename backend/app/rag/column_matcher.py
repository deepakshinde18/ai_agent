from dataclasses import dataclass

from app.rag.chroma_client import get_column_collection
from app.rag.embeddings import embed_query


@dataclass
class ColumnMatch:
    column_name: str
    table: str
    data_type: str
    confidence: float


def match_column(column_hint: str, target_type: str, n_results: int = 3) -> ColumnMatch | None:
    """RAG-resolve a free-text column hint (e.g. "account balance") to the exact
    target-DB column name, restricted to the table(s) for the given target_type.

    This is one of two gates on which SQL identifiers can be interpolated --
    the caller (fill_slots) must ALSO cross-check the result against the
    insight's slot_definitions whitelist before using it in a query.
    """
    collection = get_column_collection()
    if collection.count() == 0:
        return None

    query_embedding = embed_query(column_hint)
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        where={"target_type": target_type},
    )

    metadatas = result["metadatas"][0] if result["metadatas"] else []
    distances = result["distances"][0] if result["distances"] else []
    if not metadatas:
        return None

    meta = metadatas[0]
    confidence = max(0.0, 1.0 - distances[0])
    return ColumnMatch(
        column_name=meta["column_name"],
        table=meta["table"],
        data_type=meta["data_type"],
        confidence=confidence,
    )
