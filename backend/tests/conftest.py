"""Test configuration: isolated database per test session."""
from __future__ import annotations

import os
import tempfile

# Must be set BEFORE app modules are imported.
_test_dir = tempfile.mkdtemp(prefix="bloodbridge-tests-")
os.environ["BLOODBRIDGE_DATABASE_URL"] = f"sqlite:///{_test_dir}/test.db"
os.environ["BLOODBRIDGE_AUTH_SECRET"] = "test-secret"
os.environ["BLOODBRIDGE_SEED_DEMO_DATA"] = "false"
os.environ["BLOODBRIDGE_APP_BASE_URL"] = "http://testserver"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_token  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    init_db()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_headers():
    from app.database import SessionLocal
    from app.models.user import User
    from app.security import hash_password
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "tests.admin@bloodbridge.demo").first()
        if not user:
            user = User(name="Test Admin", email="tests.admin@bloodbridge.demo",
                        password_hash=hash_password("testpass123"), role="admin",
                        email_verified=True)
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_token(user.id, user.role)
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}
