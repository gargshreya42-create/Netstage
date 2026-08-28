"""
Shared pytest fixtures.

Uses a temporary on-disk SQLite file (not the dev netsage.db) so tests never
touch real data, and overrides the `get_db` dependency so the FastAPI test
client uses that isolated database.
"""
import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="function")
def test_db():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield TestSessionLocal

    app.dependency_overrides.clear()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope="function")
def client(test_db):
    """
    Standard test client. Clears the cached Settings and forces AI off by
    default so tests are deterministic regardless of the host environment's
    OPENAI_API_KEY — tests that specifically need AI behavior mock the
    provider directly (see test_ai_engine.py).
    """
    from app.config import get_settings

    get_settings.cache_clear()
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()

    yield TestClient(app)

    get_settings.cache_clear()


@pytest.fixture(scope="function")
def seeded_client(client):
    """A client whose DB already has the 30-case dataset loaded."""
    from app.database.session import get_db
    from app.services.case_service import seed_cases_from_csv

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    seed_cases_from_csv(db)
    db.close()
    return client
