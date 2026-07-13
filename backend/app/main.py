from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.api.health_router import router as health_router
from app.api.insight_router import router as insight_router
from app.auth.router import router as auth_router
from app.config import get_settings
from app.graph.build import compile_graph
from app.logging_conf import configure_logging, get_logger
from app.middleware.error_handlers import register_error_handlers
from app.middleware.request_id import RequestIdMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    async with AsyncPostgresSaver.from_conn_string(settings.agent_database_dsn) as checkpointer:
        await checkpointer.setup()  # idempotent; creates checkpoint tables outside Alembic's graph
        app.state.graph = compile_graph(checkpointer)
        logger.info("agent_graph_ready")
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Insight Agent", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(insight_router)

    return app


app = create_app()
