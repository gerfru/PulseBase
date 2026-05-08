import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_USER


# ── Public Routes ─────────────────────────────────────────────────────────────


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_login_page(client):
    r = await client.get("/login")
    assert r.status_code == 200


async def test_register_page(client):
    r = await client.get("/register")
    assert r.status_code == 200


# ── Auth Guard ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/dashboard",
        "/api/activities",
        "/api/readiness",
        "/api/ml-insights",
        "/api/sleep",
        "/api/hrv",
    ],
)
async def test_unauthenticated_redirects_to_login(client, path):
    r = await client.get(path)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


# ── Login / Register Validation ───────────────────────────────────────────────


async def test_login_wrong_credentials_returns_400(client):
    with patch("src.main.get_user_by_email", AsyncMock(return_value=None)):
        r = await client.post(
            "/login",
            data={
                "email": "wrong@example.com",
                "password": "wrong",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 400


async def test_register_password_mismatch_returns_400(client):
    r = await client.post(
        "/register",
        data={
            "name": "Test",
            "email": "new@example.com",
            "password": "secret123",  # pragma: allowlist secret
            "password_confirm": "different",  # pragma: allowlist secret
        },
    )
    assert r.status_code == 400


async def test_register_short_password_returns_400(client):
    r = await client.post(
        "/register",
        data={
            "name": "Test",
            "email": "new@example.com",
            "password": "short",  # pragma: allowlist secret
            "password_confirm": "short",  # pragma: allowlist secret
        },
    )
    assert r.status_code == 400


# ── Authenticated API ─────────────────────────────────────────────────────────


async def test_readiness_authenticated(client):
    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.get_readiness", AsyncMock(return_value={"score": 75})),
    ):
        r = await client.get("/api/readiness")
    assert r.status_code == 200


async def test_activities_authenticated(client):
    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.get_recent_activities", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/activities")
    assert r.status_code == 200


async def test_activity_detail_not_found(client):
    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.get_activity_detail", AsyncMock(return_value=None)),
    ):
        r = await client.get("/api/activities/999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


async def test_ml_insights_authenticated(client):
    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.get_ml_insights", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/ml-insights")
    assert r.status_code == 200


async def test_ml_status_unauthenticated(client):
    r = await client.get("/api/ml-status")
    assert r.status_code == 303


async def test_ml_status_authenticated(client):
    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.main.get_ml_status",
            AsyncMock(return_value={"pending": False, "last_ml_at": None}),
        ),
    ):
        r = await client.get("/api/ml-status")
    assert r.status_code == 200
    assert "pending" in r.json()
