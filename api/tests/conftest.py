import os

# Must be set before src.main is imported so Settings() reads them
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_APP_USER", "test")
os.environ.setdefault("DB_APP_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test-secret-key-for-testing-only!")
os.environ.setdefault("HTTPS_ONLY", "false")

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from src.main import app

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
}

TEST_USER_EPILEPSY = {**TEST_USER, "epilepsy_mode": True}
TEST_USER_GARMIN = {
    **TEST_USER,
    "garmin_linked": True,
    "garmin_email": "test@garmin.com",
}


@pytest.fixture
async def client():
    with patch("src.main.get_pool", AsyncMock(return_value=AsyncMock())):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
