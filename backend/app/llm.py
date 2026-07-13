from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import get_settings


@lru_cache
def get_chat_model(temperature: float = 0.0, streaming: bool = False) -> ChatOpenAI:
    """Chat model bound to Azure OpenAI via its OpenAI-SDK-compatible /openai/v1
    surface. `model` is the Azure *deployment name*, not a base model id.
    """
    settings = get_settings()
    return ChatOpenAI(
        base_url=settings.azure_openai_base_url,
        api_key=settings.azure_openai_api_key,
        model=settings.azure_openai_chat_deployment,
        temperature=temperature,
        streaming=streaming,
    )
