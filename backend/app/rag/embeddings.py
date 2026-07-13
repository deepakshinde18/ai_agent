from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from app.config import get_settings


@lru_cache
def get_embeddings_client() -> OpenAIEmbeddings:
    """Azure OpenAI embeddings (text-embedding-3-small by default) accessed via
    the OpenAI-SDK-compatible /openai/v1 surface. Used at both Chroma seed time
    and query time so the two always agree on model/dimensionality.
    """
    settings = get_settings()
    return OpenAIEmbeddings(
        base_url=settings.azure_openai_base_url,
        api_key=settings.azure_openai_api_key,
        model=settings.azure_openai_embedding_deployment,
    )


def embed_query(text: str) -> list[float]:
    return get_embeddings_client().embed_query(text)


def embed_documents(texts: list[str]) -> list[list[float]]:
    return get_embeddings_client().embed_documents(texts)
