import pytest
from sqlmodel import SQLModel

from app.core.security import cleanup_session_token, generate_session_token
from app.database.engine import engine, run_migrations
from app.database.models import *  # noqa: F401, F403
from app.database.seed_agents import seed_scenario_agents_if_empty
from app.database.seed_characters import seed_characters_if_empty


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Guarantees SQLite database schema is fully created before any tests execute."""
    print("\n[Pytest CI Setup] Initializing test database schema...")

    # 1. Apply Alembic migrations if migration files exist
    try:
        run_migrations()
    except Exception as e:
        print(f"[Pytest CI Setup] Alembic run note: {e}")

    # 2. Ensure all SQLModel table metadata is created in SQLite
    SQLModel.metadata.create_all(engine)

    # 3. Seed starter personas and agents
    seed_characters_if_empty()
    seed_scenario_agents_if_empty()
    print("[Pytest CI Setup] ✅ Test database schema and seeds ready.\n")
    yield


@pytest.fixture(autouse=True)
def setup_auth_token():
    """Generates an ephemeral authorization token for each test run."""
    token = generate_session_token()
    yield token
    cleanup_session_token()
