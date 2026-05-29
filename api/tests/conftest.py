import json
import os
from base64 import b64encode
from datetime import datetime, timezone

# Must be set before src.main is imported so Settings() reads them
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_APP_USER", "test")
os.environ.setdefault("DB_APP_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test-secret-key-for-testing-only!")
os.environ.setdefault("HTTPS_ONLY", "false")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from src.main import app


def make_session(client, user_id: int = 1) -> None:
    """Inject a signed session cookie into the test client (shared helper)."""
    from itsdangerous import TimestampSigner
    from src.deps import settings

    signer = TimestampSigner(settings.session_secret)
    data = b64encode(json.dumps({"user_id": str(user_id)}).encode("utf-8"))
    signed = signer.sign(data).decode("utf-8")
    client.cookies.set("session", signed)


TEST_USER = {
    "id": 1,
    "name": "Test User",
    "email": "test@example.com",
    "garmin_linked": False,
    "garmin_email": None,
    "epilepsy_mode": False,
    "spo2_enabled": False,
    "date_of_birth": None,
    "sex": None,
    "failed_login_attempts": 0,
    "locked_until": None,
    "email_verified_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
}

TEST_USER_EPILEPSY = {**TEST_USER, "epilepsy_mode": True}
TEST_USER_GARMIN = {
    **TEST_USER,
    "garmin_linked": True,
    "garmin_email": "test@garmin.com",
}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from src.deps import limiter

    limiter._storage.reset()


@pytest.fixture
async def client():
    with patch("src.main.get_pool", AsyncMock(return_value=AsyncMock())):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
