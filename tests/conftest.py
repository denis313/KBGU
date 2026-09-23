import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://calorie:calorie@localhost:5432/calorie_tracker_test"
)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", os.environ["DATABASE_URL"])
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:TEST-TOKEN"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "test-webhook-secret"
os.environ["WEBAPP_URL"] = "https://tracker.example.com"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.__main__ import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    """Fresh schema via the real Alembic migrations, plus the seeded catalogue."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(Config("alembic.ini"), "head")
    with SessionLocal() as db:
        seed(db)
    yield


@pytest.fixture(autouse=True)
def clean_users():
    yield
    with engine.begin() as conn:
        # Not TRUNCATE ... CASCADE: that would also wipe the shared catalogue via foods.owner_id.
        # ON DELETE CASCADE removes each user's profile, diary, plans and custom foods.
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("ALTER SEQUENCE users_id_seq RESTART"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


PROFILE = {
    "sex": "female",
    "birth_date": "1994-05-10",
    "height_cm": 168,
    "weight_kg": 68,
    "activity_level": "light",
    "goal": "lose",
    "weekly_rate_kg": 0.5,
    "diet_type": "omnivore",
    "excluded_allergens": [],
    "meals_per_day": 4,
}


@pytest.fixture
def auth(client) -> dict[str, str]:
    r = client.post("/api/auth/register", json={"email": "anna@example.com", "password": "secret123", "name": "Anna"})
    assert r.status_code == 201, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.put("/api/profile", json=PROFILE, headers=headers).status_code == 200
    return headers
