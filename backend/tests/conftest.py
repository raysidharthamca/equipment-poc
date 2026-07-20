"""Pytest fixtures. Every test runs against an isolated temporary SQLite file,
so the suite NEVER touches the real poc.db.

DATABASE_URL is pinned to a temp file *before* any app module is imported, so
the app engine binds to the throwaway database. ANTHROPIC_API_KEY (from a real
.env, if present) is left untouched so the `live` tests can use it.
"""
from __future__ import annotations

import os
import tempfile

# Pin a throwaway DB before importing app modules (which build the engine at
# import time from settings.DATABASE_URL). override=False in load_dotenv means
# this wins over any DATABASE_URL in .env.
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"

import pytest  # noqa: E402

from app.database import Base, SessionLocal, engine, init_db  # noqa: E402


@pytest.fixture
def db():
    """Fresh schema per test; yields a Session that is always closed."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_TMP_DB.name)
    except OSError:
        pass
