from app.rag.chroma_client import get_column_collection, stable_id


def get_column_context(table: str, column_name: str) -> str | None:
    """Direct (non-fuzzy) lookup of the seeded column_metadata document for an
    exact (table, column_name). The column name itself always comes from the
    insight's slot_definitions whitelist -- this only supplies a description
    + synonyms so the sql_builder LLM call has real grounding for how a user
    might refer to that column.
    """
    collection = get_column_collection()
    result = collection.get(ids=[stable_id(table, column_name)], include=["documents"])
    documents = result.get("documents") or []
    return documents[0] if documents else None
