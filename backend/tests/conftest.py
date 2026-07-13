"""Integration tests in this package need a reachable Postgres matching the
AGENT_DATABASE_URL(_SYNC) in backend/.env (run `alembic upgrade head` first).
Pure-logic tests (test_sql_builder.py, most of test_graph_nodes.py) don't
need a DB and will pass without one.
"""

import asyncio

import pytest
from starlette.testclient import TestClient

from app.db.session import agent_engine
from app.db.target_session import target_engine
from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    # Each TestClient(app) `with` block runs its own event loop, but
    # agent_engine/target_engine are process-wide singletons (correct in
    # production, where there's exactly one loop for the process lifetime).
    # Dispose their pools here so the next test's loop doesn't inherit
    # asyncpg connections bound to this test's now-closed loop.
    asyncio.run(agent_engine.dispose())
    asyncio.run(target_engine.dispose())
