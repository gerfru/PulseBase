import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_USER, TEST_USER_EPILEPSY


# ── Root redirect ─────────────────────────────────────────────────────────────


async def test_root_redirects_to_dashboard(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"


# ── Standard pages ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/dashboard",
        "/settings",
        "/garmin/link",
        "/libre/link",
    ],
)
async def test_authenticated_page_returns_200(client, path):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get(path)
    assert r.status_code == 200


# ── ML detail pages ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path,location",
    [
        ("/ml/anomaly", "/metrics/hr-zscore"),
        ("/ml/readiness", "/metrics/readiness-rf"),
        ("/ml/correlations", "/metrics/correlations"),
        ("/ml/battery", "/metrics/battery-pattern"),
    ],
)
async def test_ml_legacy_routes_redirect(client, path, location):
    r = await client.get(path)
    assert r.status_code == 301
    assert r.headers["location"] == location


# ── Metrics pages ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    [
        "steps",
        "sleep",
        "hrv",
        "body-battery",
        "readiness",
        "physical",
        "autonomic",
        "cognitive",
        "training-status",
    ],
)
async def test_metrics_valid_name_returns_200(client, name):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get(f"/metrics/{name}")
    assert r.status_code == 200


async def test_metrics_invalid_name_redirects_to_dashboard(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/metrics/not-a-real-metric")
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"


async def test_metrics_overview_returns_200(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/metrics")
    assert r.status_code == 200


# ── Activity detail page ──────────────────────────────────────────────────────


async def test_activity_page_not_found_redirects_to_dashboard(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.pages.get_activity_detail", AsyncMock(return_value=None)),
    ):
        r = await client.get("/activity/999")
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"


async def test_activity_page_renders_when_found(client):
    mock_activity = {
        "id": 1,
        "sport_type": "running",
        "started_at": "2026-01-01T08:00:00",
        "distance_meters": 5000.0,
        "duration_seconds": 1800,
        "avg_hr": 145,
        "calories": 400,
        "records": [],
    }
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.pages.get_activity_detail",
            AsyncMock(return_value=mock_activity),
        ),
    ):
        r = await client.get("/activity/1")
    assert r.status_code == 200


# ── Epilepsy page ─────────────────────────────────────────────────────────────


async def test_epilepsy_page_without_mode_redirects_to_settings(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/epilepsy")
    assert r.status_code == 303
    assert r.headers["location"] == "/settings"


async def test_epilepsy_page_with_mode_returns_200(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)):
        r = await client.get("/epilepsy")
    assert r.status_code == 200
