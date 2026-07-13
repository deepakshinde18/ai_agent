"""Idempotent CLI that seeds the two Chroma collections from the YAML files in
this directory. Safe to re-run: uses deterministic IDs so re-seeding upserts
rather than duplicates.

Usage:
    uv run python -m seed.seed_chroma
"""

import hashlib
from pathlib import Path

import yaml

from app.logging_conf import configure_logging, get_logger
from app.rag.chroma_client import get_column_collection, get_intent_collection
from app.rag.embeddings import embed_documents

SEED_DIR = Path(__file__).parent
logger = get_logger(__name__)


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()[:24]


def seed_intents() -> None:
    data = yaml.safe_load((SEED_DIR / "intent_examples.yaml").read_text())
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for intent in data["intents"]:
        insight_type = intent["insight_type"]
        for example in intent["examples"]:
            ids.append(_stable_id(insight_type, example))
            documents.append(example)
            metadatas.append({"insight_type": insight_type})

    embeddings = embed_documents(documents)
    get_intent_collection().upsert(
        ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings
    )
    logger.info("seeded_intent_examples", count=len(documents))


def seed_columns() -> None:
    data = yaml.safe_load((SEED_DIR / "column_metadata.yaml").read_text())
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for col in data["columns"]:
        synonyms = ", ".join(col.get("synonyms", []))
        document = f"{col['column_name']}: {col['description']}. synonyms: {synonyms}"
        ids.append(_stable_id(col["table"], col["column_name"]))
        documents.append(document)
        metadatas.append(
            {
                "table": col["table"],
                "column_name": col["column_name"],
                "data_type": col["data_type"],
                "target_type": col["target_type"],
            }
        )

    embeddings = embed_documents(documents)
    get_column_collection().upsert(
        ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings
    )
    logger.info("seeded_column_metadata", count=len(documents))


def main() -> None:
    configure_logging()
    seed_intents()
    seed_columns()
    logger.info("seed_chroma_complete")


if __name__ == "__main__":
    main()
