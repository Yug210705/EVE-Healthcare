import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import *  # noqa: F401, F403

# ── Test database setup ────────────────────────────────────────────────────

_test_engine = create_engine(settings.TEST_DATABASE_URL, pool_pre_ping=True)
TestSession = sessionmaker(bind=_test_engine, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables once per test session, drop when done."""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all tables between tests for isolation."""
    yield
    session = TestSession()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def db():
    """Provide a direct database session for state assertions in tests."""
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    """TestClient with DB dependency overridden to use test database."""

    def _override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Helper fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def seed_centres(db):
    """Insert seed diagnostic centres + tests, return the created IDs."""
    from decimal import Decimal
    from app.models.diagnostic_centre import DiagnosticCentre
    from app.models.diagnostic_test import DiagnosticTest

    centre = DiagnosticCentre(
        name="TestCentre",
        address="123 Test St",
        city="TestCity",
    )
    db.add(centre)
    db.flush()

    test_a = DiagnosticTest(
        centre_id=centre.id,
        name="Blood Test",
        description="Basic blood test",
        price=Decimal("500.00"),
    )
    test_b = DiagnosticTest(
        centre_id=centre.id,
        name="X-Ray",
        description="Chest X-Ray",
        price=Decimal("1200.00"),
    )
    db.add_all([test_a, test_b])
    db.commit()
    db.refresh(centre)
    db.refresh(test_a)
    db.refresh(test_b)

    return {"centre_id": centre.id, "test_a_id": test_a.id, "test_b_id": test_b.id}


@pytest.fixture()
def registered_user(client):
    """Register a user and return their credentials + token."""
    resp = client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "securepassword123",
            "full_name": "Test User",
        },
    )
    assert resp.status_code == 201
    user_data = resp.json()

    resp = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "securepassword123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    return {"user": user_data, "token": token}


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
