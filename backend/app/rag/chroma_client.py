from functools import lru_cache

import chromadb
from chromadb.api.models.Collection import Collection

from app.config import get_settings

INTENT_COLLECTION_NAME = "intent_examples"
COLUMN_COLLECTION_NAME = "column_metadata"


@lru_cache
def get_chroma_client() -> chromadb.ClientAPI:
    settings = get_settings()
    return chromadb.PersistentClient(path=settings.chroma_persist_dir)


def get_intent_collection() -> Collection:
    # embedding_function=None: embeddings are always computed explicitly via
    # app.rag.embeddings so seed-time and query-time use the same Azure model.
    # hnsw:space="cosine" so query distances are directly 1 - cosine_similarity.
    return get_chroma_client().get_or_create_collection(
        name=INTENT_COLLECTION_NAME,
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )


def get_column_collection() -> Collection:
    return get_chroma_client().get_or_create_collection(
        name=COLUMN_COLLECTION_NAME,
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )
