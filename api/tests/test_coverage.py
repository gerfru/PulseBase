"""
Targeted tests to reach 100% coverage on main.py.
Covers branches not exercised by the broader test suite.
"""

import base64
import json
import sys
import tempfile
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import TEST_USER


# ── _get_real_ip ──────────────────────────────────────────────────────────────


def test_get_real_ip_uses_x_forwarded_for():
    from src.deps import _get_real_ip

    class FakeRequest:
        headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        client = None

    assert _get_real_ip(FakeRequest()) == "1.2.3.4"


def test_is_trusted_proxy_invalid_host_returns_false():
    """Non-IP strings (hostnames, empty strings) trigger ValueError → False."""
    from src.deps import _is_trusted_proxy

    assert _is_trusted_proxy("not-an-ip") is False
    assert _is_trusted_proxy("traefik.home.lab") is False
    assert _is_trusted_proxy("") is False


# ── _rate_limit_exceeded_handler ──────────────────────────────────────────────


async def test_rate_limit_exceeded_handler_returns_429():
    from src.deps import _rate_limit_exceeded_handler

    r = await _rate_limit_exceeded_handler(MagicMock(), MagicMock())
    assert r.status_code == 429
    assert r.body  # JSONResponse body is set


# ── require_user — user_id in session but not in DB ──────────────────────────


async def test_require_user_user_not_found_raises_needs_login():
    from src.deps import require_user, NeedsLogin

    class FakeRequest:
        session = {"user_id": 99}

    with patch("src.deps.get_user_by_id", AsyncMock(return_value=None)):
        with pytest.raises(NeedsLogin):
            await require_user(FakeRequest())


async def test_require_user_returns_user_when_found():
    from src.deps import require_user

    class FakeRequest:
        session = {"user_id": 1}

    with patch("src.deps.get_user_by_id", AsyncMock(return_value=TEST_USER)):
        result = await require_user(FakeRequest())
    assert result == TEST_USER


async def test_require_user_rejects_unverified_email_user():
    """L-05: get_user_by_id filters by email_verified_at IS NOT NULL;
    an unverified user resolves to None which triggers NeedsLogin."""
    from src.deps import require_user, NeedsLogin

    class FakeRequest:
        session = {"user_id": 1}

    with patch("src.deps.get_user_by_id", AsyncMock(return_value=None)):
        with pytest.raises(NeedsLogin):
            await require_user(FakeRequest())


# ── garmin_link — success path ────────────────────────────────────────────────


async def test_garmin_link_success_redirects(client):
    mock_gc = MagicMock()
    mock_gc.connect = MagicMock()

    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.garmin.GarminClient", return_value=mock_gc),
        patch("src.routes.garmin.get_user_token", AsyncMock(return_value=None)),
        patch("src.routes.garmin.save_user_token", AsyncMock(return_value=None)),
        patch("src.routes.garmin.serialize_token_dir", return_value=b"{}"),
        patch("src.routes.garmin.set_garmin_linked", AsyncMock(return_value=None)),
        patch("src.routes.garmin.request_sync", AsyncMock(return_value=None)),
    ):
        r = await client.post(
            "/garmin/link",
            data={
                "garmin_email": "test@garmin.com",
                "garmin_password": "testpass123",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303
    assert r.headers["location"] == "/?linked=1"


# ── libre_link — three paths ──────────────────────────────────────────────────


def _make_fake_libre(authenticate_side_effect=None):
    """Build a fake libre.client module for sys.modules injection."""
    fake = types.ModuleType("libre.client")
    LibreAuthError = type("LibreAuthError", (Exception,), {})
    fake.LibreAuthError = LibreAuthError
    if authenticate_side_effect is not None:
        fake.authenticate = MagicMock(side_effect=authenticate_side_effect)
    else:
        mock_client = MagicMock()
        mock_client.token = "test-libre-token-abc123"  # pragma: allowlist secret
        fake.authenticate = MagicMock(return_value=mock_client)
    return fake


async def test_libre_link_success_redirects(client):
    fake = _make_fake_libre()
    with (
        patch.dict(sys.modules, {"libre.client": fake}),
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.libre.save_user_token", AsyncMock(return_value=None)),
        patch("src.routes.libre.set_libre_linked", AsyncMock(return_value=None)),
    ):
        r = await client.post(
            "/libre/link",
            data={
                "libre_email": "test@libre.com",
                "libre_password": "pass123",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"


async def test_libre_link_auth_error_returns_400(client):
    fake = _make_fake_libre()
    fake.authenticate = MagicMock(
        side_effect=fake.LibreAuthError("invalid credentials")
    )
    with (
        patch.dict(sys.modules, {"libre.client": fake}),
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
    ):
        r = await client.post(
            "/libre/link",
            data={
                "libre_email": "test@libre.com",
                "libre_password": "wrong",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 400


async def test_libre_link_generic_error_returns_400(client):
    fake = _make_fake_libre(authenticate_side_effect=Exception("network error"))
    with (
        patch.dict(sys.modules, {"libre.client": fake}),
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
    ):
        r = await client.post(
            "/libre/link",
            data={
                "libre_email": "test@libre.com",
                "libre_password": "pass",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 400


# ── libre_link — H-20/H-21: tempdir + encryption always used ─────────────────


async def test_libre_link_uses_tempdir_not_permanent_path(client):
    """H-20: libre_link must use TemporaryDirectory, not a permanent /app/tokens/ path."""
    fake = _make_fake_libre()
    captured: list = []

    def fake_tempdir(*args, **kwargs):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value="/tmp/fake_tmpdir")
        ctx.__exit__ = MagicMock(return_value=False)
        captured.append(True)
        return ctx

    with (
        patch.dict(sys.modules, {"libre.client": fake}),
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.libre.tempfile.TemporaryDirectory", side_effect=fake_tempdir),
        patch("src.routes.libre.save_user_token", AsyncMock(return_value=None)),
        patch("src.routes.libre.set_libre_linked", AsyncMock(return_value=None)),
    ):
        r = await client.post(
            "/libre/link",
            data={
                "libre_email": "test@libre.com",
                "libre_password": "pass",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303
    assert captured, "TemporaryDirectory was not called — permanent path still in use"


async def test_libre_link_always_encrypts_token(client):
    """H-21: The else-plaintext branch must no longer exist; fernet_encrypt always called."""
    fake = _make_fake_libre()
    encrypt_calls: list = []

    def mock_encrypt(data, key):
        encrypt_calls.append((data, key))
        return b"encrypted-blob"

    with (
        patch.dict(sys.modules, {"libre.client": fake}),
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.libre.fernet_encrypt", side_effect=mock_encrypt),
        patch("src.routes.libre.save_user_token", AsyncMock(return_value=None)),
        patch("src.routes.libre.set_libre_linked", AsyncMock(return_value=None)),
    ):
        r = await client.post(
            "/libre/link",
            data={
                "libre_email": "test@libre.com",
                "libre_password": "pass",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303
    assert len(encrypt_calls) == 1, "fernet_encrypt must be called exactly once"


# ── libre_unlink — token dir exists ──────────────────────────────────────────


async def test_libre_unlink_removes_existing_token_dir(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.libre.set_libre_unlinked", AsyncMock(return_value=None)),
        patch("pathlib.Path.exists", return_value=True),
        patch("shutil.rmtree"),
    ):
        r = await client.post("/libre/unlink", data={"csrf_token": ""})
    assert r.status_code == 303


# ── profile validators — valid values ────────────────────────────────────────


async def test_profile_update_valid_sex(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_health.update_user_profile", AsyncMock(return_value=None)
        ),
    ):
        r = await client.patch("/api/profile", json={"sex": "m"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_profile_update_valid_dob(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_health.update_user_profile", AsyncMock(return_value=None)
        ),
    ):
        r = await client.patch("/api/profile", json={"date_of_birth": "1990-06-15"})
    assert r.status_code == 200


async def test_profile_update_spo2_enabled(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_health.update_spo2_enabled", AsyncMock(return_value=None)
        ),
    ):
        r = await client.patch("/api/profile", json={"spo2_enabled": True})
    assert r.status_code == 200


# ── seizure validator — valid severity ───────────────────────────────────────


async def test_seizure_valid_severity(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_seizures.save_seizure", AsyncMock(return_value=1)),
    ):
        r = await client.post(
            "/api/seizures",
            json={"occurred_at": "2026-05-01T10:00:00Z", "severity": 3},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── crypto: fernet round-trip ─────────────────────────────────────────────────


def _test_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def test_fernet_encrypt_decrypt_roundtrip():
    from src.crypto import fernet_decrypt, fernet_encrypt

    key = _test_key()
    plaintext = b"secret token data"
    assert fernet_decrypt(fernet_encrypt(plaintext, key), key) == plaintext


def test_serialize_restore_token_dir_roundtrip():
    from src.crypto import restore_token_dir, serialize_token_dir

    with tempfile.TemporaryDirectory() as src_dir:
        (open(f"{src_dir}/oauth2_token.json", "wb")).write(b'{"token":"abc"}')

        blob = serialize_token_dir(src_dir)

        with tempfile.TemporaryDirectory() as dst_dir:
            restore_token_dir(blob, dst_dir)
            restored = open(f"{dst_dir}/oauth2_token.json", "rb").read()

    assert restored == b'{"token":"abc"}'


def test_serialize_token_dir_empty_dir():
    from src.crypto import serialize_token_dir

    with tempfile.TemporaryDirectory() as d:
        blob = serialize_token_dir(d)
    assert json.loads(blob) == {}


# ── garmin_link — existing token loaded from DB ───────────────────────────────


async def test_garmin_link_loads_existing_token(client):
    """When a DB token exists, it is decrypted and restored before re-linking."""
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    raw_blob = json.dumps(
        {"oauth2_token.json": base64.b64encode(b"tok").decode()}
    ).encode()
    encrypted_blob = Fernet(key.encode()).encrypt(raw_blob)

    mock_gc = MagicMock()
    mock_gc.connect = MagicMock()
    mock_settings = MagicMock()
    mock_settings.fernet_key = key

    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.garmin.GarminClient", return_value=mock_gc),
        patch(
            "src.routes.garmin.get_user_token", AsyncMock(return_value=encrypted_blob)
        ),
        patch("src.routes.garmin.save_user_token", AsyncMock(return_value=None)),
        patch("src.routes.garmin.serialize_token_dir", return_value=b"{}"),
        patch("src.routes.garmin.set_garmin_linked", AsyncMock(return_value=None)),
        patch("src.routes.garmin.request_sync", AsyncMock(return_value=None)),
        patch("src.deps.settings", mock_settings),
    ):
        r = await client.post(
            "/garmin/link",
            data={
                "garmin_email": "test@garmin.com",
                "garmin_password": "testpass123",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303


# ── Evidence Catalog ──────────────────────────────────────────────────────────


# ── restore_token_dir — path traversal protection ────────────────────────────


def test_restore_token_dir_rejects_path_traversal():
    """Files with path-traversal components must not be written outside target_dir."""
    import tempfile
    from pathlib import Path
    from src.crypto import restore_token_dir

    with tempfile.TemporaryDirectory() as target_dir:
        malicious_blob = json.dumps(
            {
                "../evil.txt": base64.b64encode(b"pwned").decode(),
                "safe.json": base64.b64encode(b"ok").decode(),
            }
        ).encode()

        restore_token_dir(malicious_blob, target_dir)

        evil_path = Path(target_dir).parent / "evil.txt"
        assert not evil_path.exists(), (
            "Path traversal must not write outside target_dir"
        )

        safe_path = Path(target_dir) / "safe.json"
        assert safe_path.exists()
        assert safe_path.read_bytes() == b"ok"


def test_restore_token_dir_rejects_absolute_path():
    """Files with absolute path names are skipped entirely."""
    import tempfile
    from pathlib import Path
    from src.crypto import restore_token_dir

    with tempfile.TemporaryDirectory() as target_dir:
        malicious_blob = json.dumps(
            {
                "/etc/cron.d/pwned": base64.b64encode(b"evil").decode(),
            }
        ).encode()

        restore_token_dir(malicious_blob, target_dir)

        assert list(Path(target_dir).iterdir()) == [], (
            "Absolute path entry must be skipped"
        )


def test_restore_token_dir_normal_filenames_written_correctly():
    """Normal filenames are written to target_dir without modification."""
    import tempfile
    from pathlib import Path
    from src.crypto import restore_token_dir

    with tempfile.TemporaryDirectory() as target_dir:
        blob = json.dumps(
            {
                "oauth2_token.json": base64.b64encode(b'{"token": "abc"}').decode(),
                "extra.bin": base64.b64encode(b"\x00\x01\x02").decode(),
            }
        ).encode()

        restore_token_dir(blob, target_dir)

        assert (
            Path(target_dir) / "oauth2_token.json"
        ).read_bytes() == b'{"token": "abc"}'
        assert (Path(target_dir) / "extra.bin").read_bytes() == b"\x00\x01\x02"


# ── FERNET_KEY validator ─────────────────────────────────────────────────────


def test_fernet_key_validator_rejects_empty_value():
    """Settings must raise ValidationError if FERNET_KEY is empty."""
    import os
    from pydantic import ValidationError

    env_overrides = {
        "DB_USER": "test",
        "DB_PASSWORD": "test",  # pragma: allowlist secret
        "DB_APP_USER": "test",
        "DB_APP_PASSWORD": "test",  # pragma: allowlist secret
        "SESSION_SECRET": "a" * 32,  # pragma: allowlist secret
        "FERNET_KEY": "",
    }
    with patch.dict(os.environ, env_overrides):
        with pytest.raises(ValidationError, match="FERNET_KEY"):
            from src.db.pool import Settings

            Settings()


def test_fernet_key_validator_accepts_valid_key():
    """Settings must accept a valid 32-byte URL-safe base64 FERNET_KEY."""
    import os
    from cryptography.fernet import Fernet

    valid_key = Fernet.generate_key().decode()
    env_overrides = {
        "DB_USER": "test",
        "DB_PASSWORD": "test",  # pragma: allowlist secret
        "DB_APP_USER": "test",
        "DB_APP_PASSWORD": "test",  # pragma: allowlist secret
        "SESSION_SECRET": "a" * 32,  # pragma: allowlist secret
        "FERNET_KEY": valid_key,
    }
    with patch.dict(os.environ, env_overrides):
        from src.db.pool import Settings

        s = Settings()  # type: ignore[call-arg]
        assert s.fernet_key == valid_key


# ── SESSION_SECRET validator ─────────────────────────────────────────────────


def test_session_secret_validator_rejects_short_value():
    """M-75: SESSION_SECRET shorter than 32 chars must raise ValidationError."""
    import os
    from pydantic import ValidationError
    from cryptography.fernet import Fernet

    env_overrides = {
        "DB_APP_USER": "test",
        "DB_APP_PASSWORD": "test",  # pragma: allowlist secret
        "SESSION_SECRET": "too-short",  # pragma: allowlist secret
        "FERNET_KEY": Fernet.generate_key().decode(),
    }
    with patch.dict(os.environ, env_overrides):
        with pytest.raises(ValidationError, match="SESSION_SECRET"):
            from src.db.pool import Settings

            Settings()


def test_session_secret_validator_accepts_32_chars():
    """M-75: SESSION_SECRET of exactly 32 characters must be accepted."""
    import os
    from cryptography.fernet import Fernet

    env_overrides = {
        "DB_APP_USER": "test",
        "DB_APP_PASSWORD": "test",  # pragma: allowlist secret
        "SESSION_SECRET": "a" * 32,  # pragma: allowlist secret
        "FERNET_KEY": Fernet.generate_key().decode(),
    }
    with patch.dict(os.environ, env_overrides):
        from src.db.pool import Settings

        s = Settings()  # type: ignore[call-arg]
        assert len(s.session_secret) == 32


# ── Evidence Catalog ──────────────────────────────────────────────────────────


def test_evidence_catalog_required_fields():
    """Every entry must have the EN 62366-inspired fields added in this sprint."""
    from src.evidence_catalog import EVIDENCE

    required = {
        "level",
        "label",
        "metric_type",
        "time_horizon",
        "intended_use",
        "not_for",
        "name",
        "summary",
        "refs",
        "limitations",
    }
    valid_types = {"recovery", "capacity", "trend", "prediction", "screening"}

    for key, entry in EVIDENCE.items():
        missing = required - set(entry.keys())
        assert not missing, f"Entry '{key}' missing fields: {missing}"
        assert entry["metric_type"] in valid_types, (
            f"Entry '{key}' has invalid metric_type: {entry['metric_type']!r}"
        )
        assert entry["time_horizon"], f"Entry '{key}' has empty time_horizon"
        assert entry["intended_use"], f"Entry '{key}' has empty intended_use"
        assert entry["not_for"], f"Entry '{key}' has empty not_for"


def test_evidence_catalog_new_entries_present():
    """Newly added metrics must have evidence entries."""
    from src.evidence_catalog import EVIDENCE

    expected_new = {
        "battery_pattern",
        "sleep_score_custom",
        "intensity_minutes_custom",
        "correlation_sleep_hrv",
    }
    for key in expected_new:
        assert key in EVIDENCE, f"Missing evidence entry for '{key}'"


def test_evidence_catalog_metric_types():
    """Spot-check metric_type assignments for correctness."""
    from src.evidence_catalog import EVIDENCE

    assert EVIDENCE["energy_physical"]["metric_type"] == "capacity"
    assert EVIDENCE["energy_autonomic"]["metric_type"] == "recovery"
    assert EVIDENCE["readiness_rf"]["metric_type"] == "prediction"
    assert EVIDENCE["battery_pattern"]["metric_type"] == "trend"
    assert EVIDENCE["anomaly_hr"]["metric_type"] == "screening"
    assert EVIDENCE["spo2_trend"]["metric_type"] == "screening"


async def test_evidence_api_returns_new_fields(client):
    """/api/evidence must return metric_type and time_horizon for every entry."""
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/api/evidence")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 17
    for key, entry in data.items():
        assert "metric_type" in entry, f"/api/evidence: '{key}' missing metric_type"
        assert "time_horizon" in entry, f"/api/evidence: '{key}' missing time_horizon"


# ── Rate Limits auf Garmin/Libre Link ────────────────────────────────────────


def test_garmin_link_has_rate_limit_decorator():
    """garmin_link POST must have a @limiter.limit decorator applied."""
    from src.routes.garmin import garmin_link

    # slowapi stores rate limit rules in _rate_limit attribute
    # Access via the underlying function if wrapped
    import inspect

    fn = garmin_link
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    # inspect.getsource includes decorator lines for the unwrapped function
    assert "5/hour" in inspect.getsource(fn), (
        "garmin_link must have @limiter.limit('5/hour') decorator"
    )
    # Structural check: the handler is in the router with POST method
    from src.routes.garmin import router

    post_routes = [
        r
        for r in router.routes
        if hasattr(r, "methods")
        and "POST" in r.methods
        and "/garmin/link" in str(r.path)
    ]
    assert len(post_routes) == 1


def test_libre_link_has_rate_limit_decorator():
    """libre_link POST must have a @limiter.limit('5/hour') decorator applied."""
    import inspect

    from src.routes.libre import libre_link, router

    fn = libre_link
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    assert "5/hour" in inspect.getsource(fn), (
        "libre_link must have @limiter.limit('5/hour') decorator"
    )
    post_routes = [
        r
        for r in router.routes
        if hasattr(r, "methods")
        and "POST" in r.methods
        and "/libre/link" in str(r.path)
    ]
    assert len(post_routes) == 1


# ── verify_csrf_token ─────────────────────────────────────────────────────────


def test_verify_csrf_token_matching_tokens():
    from src.deps import verify_csrf_token

    class FakeRequest:
        session = {"csrf_token": "secure-token-abc"}

    assert verify_csrf_token(FakeRequest(), "secure-token-abc") is True


def test_verify_csrf_token_mismatched_tokens():
    from src.deps import verify_csrf_token

    class FakeRequest:
        session = {"csrf_token": "correct-token"}

    assert verify_csrf_token(FakeRequest(), "wrong-token") is False


def test_verify_csrf_token_empty_session():
    from src.deps import verify_csrf_token

    class FakeRequest:
        session = {}

    assert verify_csrf_token(FakeRequest(), "any-token") is False


def test_verify_csrf_token_none_form_token():
    from src.deps import verify_csrf_token

    class FakeRequest:
        session = {"csrf_token": "abc123"}

    assert verify_csrf_token(FakeRequest(), None) is False


# ── _verify_reset_token ───────────────────────────────────────────────────────


async def test_internal_verify_reset_token_found():
    with patch("src.auth_tokens.get_reset_token_user_id", AsyncMock(return_value=42)):
        from src.routes.auth import _verify_reset_token

        result = await _verify_reset_token("test-token-xyz")
    assert result == 42


async def test_internal_verify_reset_token_not_found():
    with patch("src.auth_tokens.get_reset_token_user_id", AsyncMock(return_value=None)):
        from src.routes.auth import _verify_reset_token

        result = await _verify_reset_token("invalid-token")
    assert result is None


# ── DB: reset token functions ─────────────────────────────────────────────────


async def test_save_reset_token_calls_pool():
    from datetime import datetime, timezone

    mock_pool = AsyncMock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=mock_pool)):
        from src.db.users import save_reset_token

        await save_reset_token(1, "hash123", datetime.now(timezone.utc))
    mock_pool.execute.assert_awaited_once()


async def test_get_reset_token_user_id_found():
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value={"id": 7})
    with patch("src.db.users.get_pool", AsyncMock(return_value=mock_pool)):
        from src.db.users import get_reset_token_user_id

        result = await get_reset_token_user_id("valid-hash")
    assert result == 7


async def test_get_reset_token_user_id_not_found():
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value=None)
    with patch("src.db.users.get_pool", AsyncMock(return_value=mock_pool)):
        from src.db.users import get_reset_token_user_id

        result = await get_reset_token_user_id("unknown-hash")
    assert result is None


async def test_clear_reset_token_calls_pool():
    mock_pool = AsyncMock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=mock_pool)):
        from src.db.users import clear_reset_token

        await clear_reset_token(1)
    mock_pool.execute.assert_awaited_once()


# ── logging_config LOG_LEVEL ──────────────────────────────────────────────────


def test_log_level_defaults_to_info():
    """M-81: Default LOG_LEVEL must be INFO when env var is absent."""
    import logging
    import os

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LOG_LEVEL", None)
        from src.logging_config import configure_logging

        configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_log_level_from_env_debug():
    """M-81: LOG_LEVEL=DEBUG must set root logger to DEBUG."""
    import logging
    import os

    with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
        from src.logging_config import configure_logging

        configure_logging()
    assert logging.getLogger().level == logging.DEBUG


# ── configure_sentry ──────────────────────────────────────────────────────────


def test_configure_sentry_noop_when_no_dsn():
    """M-11: configure_sentry must not call sentry_sdk.init when SENTRY_DSN is not set."""
    with patch("sentry_sdk.init") as mock_init:
        settings = MagicMock()
        settings.sentry_dsn = ""
        from src.logging_config import configure_sentry

        configure_sentry(settings)
        mock_init.assert_not_called()


def test_configure_sentry_no_pii_when_dsn_set():
    """M-11: configure_sentry must set send_default_pii=False."""
    with patch("sentry_sdk.init") as mock_init:
        settings = MagicMock()
        settings.sentry_dsn = "https://x@sentry.io/1"
        from src.logging_config import configure_sentry

        configure_sentry(settings)
        mock_init.assert_called_once()
        assert mock_init.call_args.kwargs["send_default_pii"] is False


# ── _sentry_error_processor (ERROR events → Sentry) ───────────────────────────


def test_sentry_processor_captures_exception_when_exc_info_true():
    from src.logging_config import _sentry_error_processor

    with patch("src.logging_config.sentry_sdk.capture_exception") as cap:
        out = _sentry_error_processor(None, "error", {"exc_info": True})
        cap.assert_called_once_with()
    assert out == {"exc_info": True}


def test_sentry_processor_captures_exc_info_tuple():
    from src.logging_config import _sentry_error_processor

    exc = (ValueError, ValueError("x"), None)
    with patch("src.logging_config.sentry_sdk.capture_exception") as cap:
        _sentry_error_processor(None, "critical", {"exc_info": exc})
        cap.assert_called_once_with(exc)


# ── auth_tokens: deletion-token helpers ───────────────────────────────────────


def test_deletion_token_roundtrip():
    from src.auth_tokens import _make_deletion_token, _verify_deletion_token

    token = _make_deletion_token(42)
    assert _verify_deletion_token(token) == 42


def test_verify_deletion_token_invalid_returns_none():
    from src.auth_tokens import _verify_deletion_token

    assert _verify_deletion_token("not-a-valid-token") is None


# ── db/users: validation guards + set_pending_deletion ────────────────────────


async def test_update_password_rejects_nonpositive_user_id():
    from src.db.users import update_password

    with pytest.raises(ValueError):
        await update_password(0, "hash")


async def test_delete_user_rejects_nonpositive_user_id():
    from src.db.users import delete_user

    with pytest.raises(ValueError):
        await delete_user(-1)


async def test_save_user_token_rejects_nonpositive_user_id():
    from src.db.users import save_user_token

    with pytest.raises(ValueError):
        await save_user_token(0, "garmin", b"token")


async def test_set_pending_deletion_executes_update():
    from src.db import users as users_mod

    pool = MagicMock()
    pool.execute = AsyncMock()
    with patch.object(users_mod, "get_pool", AsyncMock(return_value=pool)):
        await users_mod.set_pending_deletion(7)
    pool.execute.assert_awaited_once()


# ── crypto: serialize skips non-file entries (e.g. subdirectories) ────────────


def test_serialize_token_dir_skips_subdirectories(tmp_path):
    from src.crypto import serialize_token_dir

    (tmp_path / "token.txt").write_bytes(b"data")
    (tmp_path / "subdir").mkdir()
    blob = serialize_token_dir(str(tmp_path))
    files = json.loads(blob)
    assert "token.txt" in files
    assert "subdir" not in files


# ── db/pool: cached pool is returned without re-creating ──────────────────────


async def test_get_pool_returns_cached_pool():
    from src.db import pool as pool_mod

    sentinel = object()
    pool_mod._pool = sentinel
    try:
        assert await pool_mod.get_pool() is sentinel
    finally:
        pool_mod._pool = None


# ── deps._get_real_ip: untrusted client → ignore X-Forwarded-For ──────────────


def test_get_real_ip_ignores_forwarded_from_untrusted_client():
    from src.deps import _get_real_ip

    class FakeClient:
        host = "8.8.8.8"

    class FakeRequest:
        client = FakeClient()
        headers = {"X-Forwarded-For": "1.2.3.4"}

    assert _get_real_ip(FakeRequest()) == "8.8.8.8"


# ── main: /api/metrics authenticated + middleware error counting ──────────────


async def test_api_metrics_authenticated_returns_signals(client):
    # Prime the module-level Process (lifespan does this in prod) so cpu_percent
    # reflects a real saturation reading rather than the always-0.0 first call.
    import src.main as main_mod

    main_mod._proc.cpu_percent(interval=None)
    with patch("src.main.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "active_requests" in body
    assert body["memory_mb"] > 0
    assert isinstance(body["cpu_percent"], float)


async def test_request_id_middleware_increments_error_on_exception():
    import src.main as main_mod

    mw = main_mod.RequestIDMiddleware(app=lambda *a, **k: None)
    before = main_mod._error_requests

    async def boom(_request):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await mw.dispatch(MagicMock(), boom)
    assert main_mod._error_requests == before + 1
