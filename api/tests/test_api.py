import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_USER, TEST_USER_EPILEPSY


# ── L1: api.py split — import smoke + route-registration ──────────────────────


def test_api_aggregator_includes_all_feature_routers():
    """ARCH-L5: api.py is now a thin aggregator over feature modules.
    Verify every sub-module imports and all expected /api/* paths are wired."""
    from src.routes import (
        api,
        api_glucose,
        api_health,
        api_ml,
        api_seizures,
    )

    # Each feature module exposes a router
    for mod in (api_health, api_ml, api_seizures, api_glucose):
        assert mod.router.routes, f"{mod.__name__} registered no routes"

    paths = {r.path for r in api.router.routes}
    for expected in (
        "/api/activities",
        "/api/daily",
        "/api/training-load",
        "/api/evidence",
        "/api/ml-insights",
        "/api/ml-feedback",
        "/api/seizures",
        "/api/seizures/risk",
        "/api/glucose",
        "/api/glucose/stats",
    ):
        assert expected in paths, f"{expected} missing from aggregator router"


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


async def test_ready_no_migrations_returns_503(client):
    pool = AsyncMock()
    pool.fetchval = AsyncMock(return_value=0)
    with patch("src.main.get_pool", AsyncMock(return_value=pool)):
        r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "no_migrations"


# ── Security Headers ──────────────────────────────────────────────────────────


async def test_security_headers_present(client):
    r = await client.get("/health")
    assert "connect-src 'self'" in r.headers.get("content-security-policy", "")
    assert "payment=()" in r.headers.get("permissions-policy", "")
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


async def test_hsts_header_set_when_https_only(client):
    from src.main import settings as main_settings

    with patch.object(main_settings, "https_only", True):
        r = await client.get("/health")
    assert "strict-transport-security" in r.headers
    assert "max-age=31536000" in r.headers["strict-transport-security"]
    assert "includeSubDomains" in r.headers["strict-transport-security"]


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
        patch(
            "src.routes.api_health.get_readiness", AsyncMock(return_value={"score": 75})
        ),
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
        # Operational
        "/api/metrics",
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
        patch(
            "src.routes.api_health.get_readiness", AsyncMock(return_value={"score": 75})
        ),
    ):
        r = await client.get("/api/readiness")
    assert r.status_code == 200


async def test_activities_authenticated(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_health.get_recent_activities", AsyncMock(return_value=[])
        ),
    ):
        r = await client.get("/api/activities")
    assert r.status_code == 200


async def test_activity_detail_not_found(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_health.get_activity_detail", AsyncMock(return_value=None)
        ),
    ):
        r = await client.get("/api/activities/999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


async def test_activity_detail_idor_returns_404(client):
    """User A requesting User B's activity ID gets 404 (not 403/200).
    DB layer enforces AND user_id = $2; route returns 404 when result is None."""
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_health.get_activity_detail", AsyncMock(return_value=None)
        ),
    ):
        r = await client.get("/api/activities/9999")
    assert r.status_code == 404


async def test_ml_insights_authenticated(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_ml.get_ml_insights", AsyncMock(return_value={})),
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
            "src.routes.api_ml.get_ml_status",
            AsyncMock(return_value={"pending": False, "last_ml_at": None}),
        ),
    ):
        r = await client.get("/api/ml-status")
    assert r.status_code == 200
    assert "pending" in r.json()


# ── SeizureBody Validierung ───────────────────────────────────────────────────


async def test_seizure_notes_too_long_rejected(client):
    """POST /api/seizures with notes > 2000 chars must return 422."""
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)):
        r = await client.post(
            "/api/seizures",
            json={
                "occurred_at": "2026-01-01T10:00:00Z",
                "notes": "x" * 2001,
            },
        )
    assert r.status_code == 422


async def test_seizure_notes_at_limit_accepted(client):
    """POST /api/seizures with notes == 2000 chars must succeed."""
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch("src.routes.api_seizures.save_seizure", AsyncMock(return_value=1)),
    ):
        r = await client.post(
            "/api/seizures",
            json={
                "occurred_at": "2026-01-01T10:00:00Z",
                "notes": "x" * 2000,
            },
        )
    assert r.status_code == 200


# ── PATCH/DELETE /api/seizures/{id} ───────────────────────────────────────────


async def test_update_seizure_success(client):
    """PATCH /api/seizures/{id} returns ok when a row was updated."""
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch("src.routes.api_seizures.update_seizure", AsyncMock(return_value=True)),
    ):
        r = await client.patch(
            "/api/seizures/5",
            json={
                "occurred_at": "2026-01-01T10:00:00Z",
                "type": "focal",
                "severity": 3,
            },
        )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "id": 5}


async def test_update_seizure_not_found_returns_404(client):
    """PATCH on a foreign/missing id returns 404 (ownership enforced in DB layer)."""
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch("src.routes.api_seizures.update_seizure", AsyncMock(return_value=False)),
    ):
        r = await client.patch(
            "/api/seizures/999",
            json={"occurred_at": "2026-01-01T10:00:00Z"},
        )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


async def test_update_seizure_invalid_type_rejected(client):
    """PATCH with an invalid type is rejected by SeizureBody validation (422)."""
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)):
        r = await client.patch(
            "/api/seizures/5",
            json={"occurred_at": "2026-01-01T10:00:00Z", "type": "bogus"},
        )
    assert r.status_code == 422


async def test_delete_seizure_success(client):
    """DELETE /api/seizures/{id} returns ok when a row was deleted."""
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch("src.routes.api_seizures.delete_seizure", AsyncMock(return_value=True)),
    ):
        r = await client.delete("/api/seizures/5")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_delete_seizure_not_found_returns_404(client):
    """DELETE on a foreign/missing id returns 404."""
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch("src.routes.api_seizures.delete_seizure", AsyncMock(return_value=False)),
    ):
        r = await client.delete("/api/seizures/999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
