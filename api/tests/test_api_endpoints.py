from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import TEST_USER, TEST_USER_EPILEPSY, TEST_USER_GARMIN


def _assert_validation_envelope(r) -> None:
    """Every 422 goes through the global RequestValidationError handler (PR-A):
    unified `{error:{code,message,details}}` form, and crucially NO `input`/`ctx`
    keys — those would echo client-submitted values (e.g. a password)."""
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"]
    for item in body["error"].get("details", []):
        assert "input" not in item
        assert "ctx" not in item


# ── Activities ────────────────────────────────────────────────────────────────


async def test_activity_detail_ok(client):
    mock = {"id": 1, "sport_type": "running", "started_at": "2026-01-01", "records": []}
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_health.get_activity_detail", AsyncMock(return_value=mock)
        ),
    ):
        r = await client.get("/api/activities/1")
    assert r.status_code == 200


async def test_rpe_valid_returns_ok(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_health.set_activity_rpe", AsyncMock(return_value=True)),
    ):
        r = await client.patch("/api/activities/1/rpe", json={"rpe": 7})
    assert r.status_code == 200
    assert r.json()["rpe"] == 7


async def test_rpe_zero_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.patch("/api/activities/1/rpe", json={"rpe": 0})
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_rpe_eleven_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.patch("/api/activities/1/rpe", json={"rpe": 11})
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_rpe_not_found_returns_404(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_health.set_activity_rpe", AsyncMock(return_value=False)),
    ):
        r = await client.patch("/api/activities/1/rpe", json={"rpe": 5})
    assert r.status_code == 404


# ── Daily / Sleep / HRV ───────────────────────────────────────────────────────


async def test_api_daily_returns_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_health.get_daily_summaries", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/daily")
    assert r.status_code == 200


async def test_api_sleep_returns_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_health.get_sleep_sessions", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/sleep")
    assert r.status_code == 200


async def test_api_hrv_returns_data(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_health.get_latest_hrv", AsyncMock(return_value=None)),
    ):
        r = await client.get("/api/hrv")
    assert r.status_code == 200


async def test_api_hrv_trend_returns_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_health.get_hrv_trend", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/hrv/trend")
    assert r.status_code == 200


# ── Training ──────────────────────────────────────────────────────────────────


async def test_api_training_status(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_health.get_latest_training_status",
            AsyncMock(return_value={}),
        ),
    ):
        r = await client.get("/api/training-status")
    assert r.status_code == 200


async def test_api_weekly_returns_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_health.get_weekly_stats", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/weekly")
    assert r.status_code == 200


async def test_api_energy_returns_data(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_health.get_energy_metrics", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/energy")
    assert r.status_code == 200


async def test_api_training_load_returns_data(client):
    mock_load = {"atl": 0, "ctl": 0, "tsb": 0, "history": []}
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_health.get_training_load_inputs", AsyncMock(return_value=[])
        ),
        patch("src.routes.api_health.get_activity_hrmax", AsyncMock(return_value=None)),
        patch("src.routes.api_health.get_user_sex", AsyncMock(return_value=None)),
        patch(
            "src.routes.api_health.build_training_load",
            MagicMock(return_value=mock_load),
        ),
    ):
        r = await client.get("/api/training-load")
    assert r.status_code == 200


# ── ML history ────────────────────────────────────────────────────────────────


async def test_api_ml_history_returns_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_ml.get_ml_history", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/ml-history")
    assert r.status_code == 200


# ── Sync ──────────────────────────────────────────────────────────────────────


async def test_api_sync_status_returns_data(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_health.get_sync_status", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/sync-status")
    assert r.status_code == 200


# ── Profile ───────────────────────────────────────────────────────────────────


async def test_profile_update_epilepsy_mode(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_health.update_epilepsy_mode", AsyncMock(return_value=None)
        ),
    ):
        r = await client.patch("/api/profile", json={"epilepsy_mode": True})
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_profile_update_invalid_sex_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.patch("/api/profile", json={"sex": "invalid"})
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_profile_update_future_dob_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.patch("/api/profile", json={"date_of_birth": "2099-01-01"})
    assert r.status_code == 422
    _assert_validation_envelope(r)


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
        r = await client.post("/garmin/unlink", data={"csrf_token": ""})
    assert r.status_code == 303


# ── LibreLinkUp link / unlink ─────────────────────────────────────────────────


async def test_libre_unlink_redirects(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.libre.set_libre_unlinked", AsyncMock(return_value=None)),
    ):
        r = await client.post("/libre/unlink", data={"csrf_token": ""})
    assert r.status_code == 303


# ── Epilepsy / Seizures ───────────────────────────────────────────────────────


async def test_seizure_create_valid(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch("src.routes.api_seizures.save_seizure", AsyncMock(return_value=1)),
    ):
        r = await client.post(
            "/api/seizures",
            json={"occurred_at": "2026-05-01T10:00:00Z", "type": "focal"},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_seizure_missing_occurred_at_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)):
        r = await client.post("/api/seizures", json={"type": "focal"})
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_update_seizure_missing_occurred_at_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)):
        r = await client.patch("/api/seizures/5", json={"type": "focal"})
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_seizure_invalid_type_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)):
        r = await client.post(
            "/api/seizures",
            json={"occurred_at": "2026-05-01T10:00:00Z", "type": "stroke"},
        )
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_seizure_invalid_severity_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)):
        r = await client.post(
            "/api/seizures",
            json={"occurred_at": "2026-05-01T10:00:00Z", "severity": 6},
        )
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_seizures_list(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch("src.routes.api_seizures.get_seizures", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/seizures")
    assert r.status_code == 200


async def test_seizures_days_zero_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)):
        r = await client.get("/api/seizures?days=0")
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_seizures_days_over_max_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)):
        r = await client.get("/api/seizures?days=366")
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_seizures_days_boundary_min(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch("src.routes.api_seizures.get_seizures", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/seizures?days=1")
    assert r.status_code == 200


async def test_seizures_days_boundary_max(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch("src.routes.api_seizures.get_seizures", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/seizures?days=365")
    assert r.status_code == 200


async def test_seizure_risk(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch("src.routes.api_seizures.get_seizure_risk", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/seizures/risk")
    assert r.status_code == 200


async def test_seizure_risk_response_has_level_and_flags(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch(
            "src.routes.api_seizures.get_seizure_risk",
            AsyncMock(return_value={"level": "ok", "flags": []}),
        ),
    ):
        r = await client.get("/api/seizures/risk")
    assert r.status_code == 200
    body = r.json()
    assert "level" in body
    assert "flags" in body


async def test_seizure_risk_warning_level(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch(
            "src.routes.api_seizures.get_seizure_risk",
            AsyncMock(
                return_value={
                    "level": "warning",
                    "flags": [{"type": "sleep_debt", "value": 5.2}],
                }
            ),
        ),
    ):
        r = await client.get("/api/seizures/risk")
    assert r.status_code == 200
    assert r.json()["level"] == "warning"
    assert len(r.json()["flags"]) == 1


async def test_seizure_risk_high_level(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_EPILEPSY)),
        patch(
            "src.routes.api_seizures.get_seizure_risk",
            AsyncMock(
                return_value={
                    "level": "high",
                    "flags": [{"type": "hrv_drop", "value": 25}],
                }
            ),
        ),
    ):
        r = await client.get("/api/seizures/risk")
    assert r.status_code == 200
    assert r.json()["level"] == "high"


# ── Epilepsy guard — must return 403 when epilepsy_mode=False ─────────────────


async def test_seizure_create_requires_epilepsy_mode(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post(
            "/api/seizures",
            json={"occurred_at": "2026-05-01T10:00:00Z", "type": "focal"},
        )
    assert r.status_code == 403


async def test_seizure_list_requires_epilepsy_mode(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/api/seizures")
    assert r.status_code == 403


async def test_seizure_update_requires_epilepsy_mode(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.patch(
            "/api/seizures/1",
            json={"occurred_at": "2026-05-01T10:00:00Z", "type": "focal"},
        )
    assert r.status_code == 403


async def test_seizure_delete_requires_epilepsy_mode(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.delete("/api/seizures/1")
    assert r.status_code == 403


async def test_seizure_risk_requires_epilepsy_mode(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/api/seizures/risk")
    assert r.status_code == 403


# ── ML Feedback ───────────────────────────────────────────────────────────────


async def test_ml_feedback_valid_returns_ok(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_ml.save_ml_feedback", AsyncMock(return_value=None)
        ) as save,
    ):
        r = await client.post(
            "/api/ml-feedback",
            json={"model": "readiness_rf", "helpful": True},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    save.assert_awaited_once_with(TEST_USER["id"], "readiness_rf", True)


async def test_ml_feedback_anomaly_model_ok(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_ml.save_ml_feedback", AsyncMock(return_value=None)),
    ):
        r = await client.post(
            "/api/ml-feedback",
            json={"model": "anomaly_hr", "helpful": False},
        )
    assert r.status_code == 200


async def test_ml_feedback_invalid_model_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post(
            "/api/ml-feedback",
            json={"model": "bogus", "helpful": True},
        )
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_ml_feedback_missing_helpful_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post("/api/ml-feedback", json={"model": "readiness_rf"})
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_ml_feedback_get_returns_map(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_ml.get_ml_feedback",
            AsyncMock(return_value={"readiness_rf": True}),
        ),
    ):
        r = await client.get("/api/ml-feedback")
    assert r.status_code == 200
    assert r.json() == {"readiness_rf": True}


# ── Glucose ───────────────────────────────────────────────────────────────────


async def test_glucose_default_returns_200(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_glucose.get_glucose_recent", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/glucose")
    assert r.status_code == 200


async def test_glucose_hours_min_boundary(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_glucose.get_glucose_recent", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/glucose?hours=1")
    assert r.status_code == 200


async def test_glucose_hours_max_boundary(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_glucose.get_glucose_recent", AsyncMock(return_value=[])),
    ):
        r = await client.get("/api/glucose?hours=168")
    assert r.status_code == 200


async def test_glucose_hours_out_of_range_returns_422(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/api/glucose?hours=0")
    assert r.status_code == 422
    _assert_validation_envelope(r)


async def test_glucose_stats_returns_200(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_glucose.get_glucose_stats", AsyncMock(return_value={})),
    ):
        r = await client.get("/api/glucose/stats")
    assert r.status_code == 200


async def test_evidence_returns_catalog(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/api/evidence")
    assert r.status_code == 200
    data = r.json()
    # ACWR entfernt — unzureichende Evidenz (Impellizzeri et al. 2020, RCT 2021 negativ)
    assert "acwr" not in data
    # Stattdessen prüfen ob Catalog-Einträge die erwartete Struktur haben
    assert len(data) > 0
    first = next(iter(data.values()))
    assert "level" in first
    assert "refs" in first


# ── Error envelope (PR-A) ─────────────────────────────────────────────────────


async def test_validation_error_does_not_leak_submitted_value(client):
    """NEU-1 regression guard: a 422 must not echo the client-submitted value
    back into the response body (it would leak a password on auth forms)."""
    canary = "leak-canary-do-not-echo"  # pragma: allowlist secret
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post(
            "/api/ml-feedback", json={"model": canary, "helpful": True}
        )
    assert r.status_code == 422
    _assert_validation_envelope(r)
    assert canary not in r.text


async def test_csrf_403_uses_error_envelope(client):
    """A raised HTTPException(403) is normalised to the unified envelope by the
    global StarletteHTTPException handler. CSRF is bypassed globally in tests
    (_bypass_csrf), so re-patch verify_csrf_token to False for this one path."""
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER_GARMIN)),
        patch("src.routes.garmin.verify_csrf_token", return_value=False),
    ):
        r = await client.post("/garmin/unlink", data={"csrf_token": "x"})
    assert r.status_code == 403
    body = r.json()
    assert body["error"]["code"] == "FORBIDDEN"
    assert body["error"]["message"]
