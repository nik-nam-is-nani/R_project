import shutil
import tempfile
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.main import app
from app.services.storage import LocalStorageProvider, get_storage_provider


@pytest.fixture(scope="function")
def temp_storage_dir() -> Generator[str, None, None]:
    """Create a temporary storage directory for isolated file operations in tests."""
    temp_dir = tempfile.mkdtemp(prefix="cert_test_storage_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def db_session(temp_storage_dir: str) -> Generator[Session, None, None]:
    """Create an isolated in-memory SQLite database session per test function."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Patch SessionLocal across processor and db modules so background tasks hit the test in-memory DB
    with patch("app.workers.processor.SessionLocal", TestingSessionLocal), \
         patch("app.db.base.SessionLocal", TestingSessionLocal):
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session, temp_storage_dir: str) -> Generator[TestClient, None, None]:
    """FastAPI TestClient fixture with overridden DB and storage dependencies."""
    test_storage = LocalStorageProvider(base_dir=temp_storage_dir)

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    def _override_get_storage():
        return test_storage

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_storage_provider] = _override_get_storage

    with patch("app.workers.processor.get_storage_provider", return_value=test_storage), \
         patch("app.services.storage.get_storage_provider", return_value=test_storage), \
         patch("app.services.storage.storage_provider", test_storage):
        with TestClient(app) as test_client:
            yield test_client

    app.dependency_overrides.clear()
