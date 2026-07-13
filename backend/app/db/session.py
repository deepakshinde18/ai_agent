from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

# Engine for the agent's own Postgres: users, insight_definitions, interactions,
# and (separately) the LangGraph checkpointer.
agent_engine = create_async_engine(settings.agent_database_url, pool_pre_ping=True)

AgentSessionLocal = async_sessionmaker(
    bind=agent_engine, expire_on_commit=False, class_=AsyncSession
)


async def get_agent_session() -> AsyncIterator[AsyncSession]:
    async with AgentSessionLocal() as session:
        yield session
