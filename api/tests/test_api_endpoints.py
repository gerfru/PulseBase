from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import TEST_USER, TEST_USER_GARMIN


# ── Activities ────────────────────────────────────────────────────────────────


async def test_activity_detail_ok(client):
    mock = {"id": 1, "sport_type": "running", "started_at": "2026-01-01", "records": []}
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_activity_detail", AsyncMock(return_value=mock)),
    ):
        r = await client.get("/api/activities/1")
    assert r.status_code == 200


async def test_rpe_valid_returns_ok(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.set_activity_rpe", AsyncMock(return_value=True)),
    ):
        r = await client.patch("/api/activities/1/rpe", json={"rpe": 7})
    assert r.status_code == 200
    assert r.json()["rpe"] == 7


async def test_rpe_zero_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.patch("/api/activities/1/rpe", json={"rpe": 0})
    assert r.status_code == 422


async def test_rpe_eleven_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.patch("/api/activities/1/rpe", json={"rpe": 11})
    assert r.status_code == 422


async def test_rpe_not_found_returns_404(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.set_activity_rpe", AsyncMock(return_value=False)),
    ):
        r = await client.patch("/api/activities/1/rpe", json={"rpe": 5})
    assert r.status_code == 404


# ── Daily / Sleep / HRV ───────────────────────────────────────────────────────


async def test_api_daily_returns_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_daily_summaries", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/daily")
    assert r.status_code == 200


async def test_api_sleep_returns_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_sleep_sessions", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/sleep")
    assert r.status_code == 200


async def test_api_hrv_returns_data(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_latest_hrv", AsyncMock(return_value=None)),
    ):
        r = await client.get("/api/hrv")
    assert r.status_code == 200


async def test_api_hrv_trend_returns_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_hrv_trend", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/hrv/trend")
    assert r.status_code == 200


# ── Training ──────────────────────────────────────────────────────────────────


async def test_api_training_status(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_latest_training_status", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/training-status")
    assert r.status_code == 200


async def test_api_weekly_returns_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_weekly_stats", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/weekly")
    assert r.status_code == 200


async def test_api_energy_returns_data(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_energy_metrics", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/energy")
    assert r.status_code == 200


async def test_api_training_load_returns_data(client):
    mock_load = {"atl": 0, "ctl": 0, "tsb": 0, "history": []}
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_training_load_inputs", AsyncMock(return_value=[])),
        patch("src.routes.api.get_activity_hrmax", AsyncMock(return_value=None)),
        patch("src.routes.api.get_user_sex", AsyncMock(return_value=None)),
        patch("src.routes.api.build_training_load", MagicMock(return_value=mock_load)),
    ):
        r = await client.get("/api/training-load")
    assert r.status_code == 200


# ── ML history ────────────────────────────────────────────────────────────────


async def test_api_ml_history_returns_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_ml_history", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/ml-history")
    assert r.status_code == 200


# ── Sync ──────────────────────────────────────────────────────────────────────


async def test_sync_not_linked_returns_400(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post("/api/sync")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "NOT_LINKED"


async def test_sync_linked_returns_requested(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_GARMIN)),
        patch("src.routes.api.request_sync", AsyncMock(return_value=None)),
    ):
        r = await client.post("/api/sync")
    assert r.status_code == 200
    assert r.json()["status"] == "requested"


async def test_api_sync_status_returns_data(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_sync_status", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/sync-status")
    assert r.status_code == 200


# ── Profile ───────────────────────────────────────────────────────────────────


async def test_profile_update_epilepsy_mode(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.update_epilepsy_mode", AsyncMock(return_value=None)),
    ):
        r = await client.patch("/api/profile", json={"epilepsy_mode": True})
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_profile_update_invalid_sex_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.patch("/api/profile", json={"sex": "invalid"})
    assert r.status_code == 422


async def test_profile_update_future_dob_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.patch("/api/profile", json={"date_of_birth": "2099-01-01"})
    assert r.status_code == 422


# ── Garmin link / unlink ──────────────────────────────────────────────────────


async def test_garmin_link_invalid_credentials_returns_400(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.garmin.GarminClient", side_effect=Exception("auth failed")),
    ):
        r = await client.post(
            "/garmin/link",
            data={
                "garmin_email": "wrong@garmin.com",
                "garmin_password": "wrongpass",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 400


async def test_garmin_unlink_redirects(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_GARMIN)),
        patch("src.routes.garmin.set_garmin_unlinked", AsyncMock(return_value=None)),
    ):
        r = await client.post("/garmin/unlink")
    assert r.status_code == 303


# ── LibreLinkUp link / unlink ─────────────────────────────────────────────────


async def test_libre_unlink_redirects(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.libre.set_libre_unlinked", AsyncMock(return_value=None)),
    ):
        r = await client.post("/libre/unlink")
    assert r.status_code == 303


# ── Epilepsy / Seizures ───────────────────────────────────────────────────────


async def test_seizure_create_valid(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.save_seizure", AsyncMock(return_value=1)),
    ):
        r = await client.post(
            "/api/seizures",
            json={"occurred_at": "2026-05-01T10:00:00Z", "type": "focal"},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_seizure_missing_occurred_at_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post("/api/seizures", json={"type": "focal"})
    assert r.status_code == 422


async def test_seizure_invalid_type_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post(
            "/api/seizures",
            json={"occurred_at": "2026-05-01T10:00:00Z", "type": "stroke"},
        )
    assert r.status_code == 422


async def test_seizure_invalid_severity_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post(
            "/api/seizures",
            json={"occurred_at": "2026-05-01T10:00:00Z", "severity": 6},
        )
    assert r.status_code == 422


async def test_seizures_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_seizures", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/seizures")
    assert r.status_code == 200


async def test_seizure_risk(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_seizure_risk", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/seizures/risk")
    assert r.status_code == 200


# ── Glucose ───────────────────────────────────────────────────────────────────


async def test_glucose_default_returns_200(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_glucose_recent", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/glucose")
    assert r.status_code == 200


async def test_glucose_hours_min_boundary(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_glucose_recent", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/glucose?hours=1")
    assert r.status_code == 200


async def test_glucose_hours_max_boundary(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_glucose_recent", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/glucose?hours=168")
    assert r.status_code == 200


async def test_glucose_hours_out_of_range_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/api/glucose?hours=0")
    assert r.status_code == 422


async def test_glucose_stats_returns_200(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api.get_glucose_stats", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/glucose/stats")
    assert r.status_code == 200


async def test_evidence_returns_catalog(client):
    r = await client.get("/api/evidence")
    assert r.status_code == 200
    data = r.json()
    assert "acwr" in data
    assert data["acwr"]["level"] == "meta"
    assert "refs" in data["acwr"]
