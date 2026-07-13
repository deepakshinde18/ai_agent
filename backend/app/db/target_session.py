from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import get_settings

settings = get_settings()

# Separate engine pointed at the business/target Postgres instance. This DB is
# expected to be provisioned with a read-only role at the database level --
# parameterized queries here protect against injection, not against an
# over-privileged connection string.
target_engine = create_async_engine(
    settings.target_database_url,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {
            "statement_timeout": str(settings.target_query_timeout_seconds * 1000)
        }
    },
)


async def get_target_connection() -> AsyncIterator[AsyncConnection]:
    async with target_engine.connect() as conn:
        yield conn
