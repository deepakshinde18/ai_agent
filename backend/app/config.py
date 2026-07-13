from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Agent's own Postgres (sessions, checkpoints, auth, audit log) --
    agent_database_url: str = Field(
        ..., description="postgresql+asyncpg://user:pass@host:port/dbname"
    )
    # Sync URL used only by Alembic (async engines aren't supported there directly).
    agent_database_url_sync: str = Field(
        ..., description="postgresql+psycopg://user:pass@host:port/dbname"
    )

    # -- Business/target Postgres (read-only queries only, separate instance) --
    target_database_url: str = Field(
        ..., description="postgresql+asyncpg://readonly_user:pass@host:port/dbname"
    )
    target_query_timeout_seconds: int = Field(default=15)

    # -- Azure OpenAI, accessed via the OpenAI-SDK-compatible /openai/v1 surface --
    azure_openai_endpoint: str = Field(
        ..., description="e.g. https://<resource>.openai.azure.com"
    )
    azure_openai_api_key: str
    azure_openai_chat_deployment: str = Field(default="gpt-4o-mini")
    azure_openai_embedding_deployment: str = Field(default="text-embedding-3-small")

    # -- Chroma --
    chroma_persist_dir: str = Field(default="./.chroma_data")
    intent_confidence_threshold: float = Field(default=0.75)
    column_match_confidence_threshold: float = Field(default=0.6)

    # -- JWT auth --
    jwt_secret_key: str
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=60)

    # -- Presidio --
    presidio_spacy_model: str = Field(default="en_core_web_lg")
    presidio_high_risk_entities: list[str] = Field(
        default_factory=lambda: [
            "US_SSN",
            "CREDIT_CARD",
            "US_BANK_NUMBER",
            "US_PASSPORT",
            "US_DRIVER_LICENSE",
            "IBAN_CODE",
            "CRYPTO",
        ]
    )

    # -- Misc --
    log_level: str = Field(default="INFO")
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @property
    def azure_openai_base_url(self) -> str:
        return f"{self.azure_openai_endpoint.rstrip('/')}"

    @property
    def agent_database_dsn(self) -> str:
        """Plain libpq conninfo string (no SQLAlchemy '+driver' suffix), for
        langgraph-checkpoint-postgres's AsyncPostgresSaver which manages its
        own psycopg connections directly.
        """
        return self.agent_database_url_sync.replace("postgresql+psycopg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
