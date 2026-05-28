import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_USER


# ── Public Routes ─────────────────────────────────────────────────────────────


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_ready_ok(client):
    r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


async def test_ready_db_failure_returns_503(client):
    with patch("src.main.get_pool", AsyncMock(side_effect=Exception("db down"))):
        r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "unavailable"


# ── Security Headers ──────────────────────────────────────────────────────────


async def test_security_headers_present(client):
    r = await client.get("/health")
    assert "connect-src 'self'" in r.headers.get("content-security-policy", "")
    assert "payment=()" in r.headers.get("permissions-policy", "")
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"


async def test_csp_no_external_font_sources(client):
    csp = (
        r.headers.get("content-security-policy", "")
        if (r := await client.get("/health"))
        else ""
    )
    assert "fonts.googleapis.com" not in csp
    assert "fonts.gstatic.com" not in csp


# ── Cache-Control Headers ─────────────────────────────────────────────────────


async def test_api_get_has_private_cache_header(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_readiness", AsyncMock(return_value={"score": 75})),
    ):
        r = await client.get("/api/readiness")
    assert r.headers.get("cache-control") == "private, no-cache"


async def test_post_has_no_store_cache_header(client):
    with patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=None)):
        r = await client.post(
            "/login",
            data={"email": "x@x.com", "password": "wrong"},  # pragma: allowlist secret
        )  # pragma: allowlist secret
    assert r.headers.get("cache-control") == "no-store"


async def test_static_asset_has_immutable_cache_header(client):
    r = await client.get("/static/style.css")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "public, max-age=31536000, immutable"


async def test_static_js_has_no_cache_header(client):
    r = await client.get("/static/colors.js")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-cache"


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
        # HTML pages
        "/",
        "/dashboard",
        "/settings",
        "/garmin/link",
        "/libre/link",
        "/metrics/steps",
        "/metrics/body-battery",
        "/activity/1",
        "/epilepsy",
        # Core JSON API
        "/api/activities",
        "/api/activities/1",
        "/api/daily",
        "/api/sleep",
        "/api/hrv",
        "/api/hrv/trend",
        "/api/training-status",
        "/api/weekly",
        "/api/readiness",
        "/api/energy",
        "/api/training-load",
        # ML endpoints
        "/ml/anomaly",
        "/ml/readiness",
        "/ml/correlations",
        "/ml/battery",
        "/api/ml-insights",
        "/api/ml-history",
        # Sync + status
        "/api/sync-status",
        "/api/ml-status",
        # Epilepsy / glucose
        "/api/seizures",
        "/api/seizures/risk",
        "/api/glucose",
        "/api/glucose/stats",
    ],
)
async def test_unauthenticated_redirects_to_login(client, path):
    r = await client.get(path)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


# ── Login / Register Validation ───────────────────────────────────────────────


async def test_login_wrong_credentials_returns_400(client):
    with patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=None)):
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
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_readiness", AsyncMock(return_value={"score": 75})),
    ):
        r = await client.get("/api/readiness")
    assert r.status_code == 200


async def test_activities_authenticated(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_recent_activities", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/activities")
    assert r.status_code == 200


async def test_activity_detail_not_found(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_activity_detail", AsyncMock(return_value=None)),
    ):
        r = await client.get("/api/activities/999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


async def test_ml_insights_authenticated(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_ml_insights", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/ml-insights")
    assert r.status_code == 200


async def test_ml_status_unauthenticated(client):
    r = await client.get("/api/ml-status")
    assert r.status_code == 303


async def test_ml_status_authenticated(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api.get_ml_status",
            AsyncMock(return_value={"pending": False, "last_ml_at": None}),
        ),
    ):
        r = await client.get("/api/ml-status")
    assert r.status_code == 200
    assert "pending" in r.json()
