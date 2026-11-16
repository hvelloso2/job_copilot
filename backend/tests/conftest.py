import os

# Tests never touch the real DB or the real API.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ANTHROPIC_MODEL"] = "test-model"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["ANTHROPIC_FALLBACKS"] = ""

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401
from app.database import Base  # noqa: E402


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
