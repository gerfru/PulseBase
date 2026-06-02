"""Tests for sync-service src/garmin/client.py — GarminClient."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from garmin.client import GarminClient


@pytest.fixture
def token_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def client(token_dir):
    return GarminClient(
        email="test@garmin.com",
        password="pass123",  # pragma: allowlist secret
        token_dir=token_dir,
    )


@pytest.fixture
def client_no_password(token_dir):
    return GarminClient(email="test@garmin.com", password="", token_dir=token_dir)


# ── connect() ────────────────────────────────────────────────────────────────


def test_connect_token_login_success(client, token_dir):
    mock_instance = MagicMock()
    with patch("garmin.client.garminconnect") as mock_gc:
        mock_gc.Garmin.return_value = mock_instance
        client.connect()
    mock_instance.login.assert_called_once_with(token_dir)


def test_connect_token_login_fails_falls_back_to_fresh_login(client, token_dir):
    mock_instance = MagicMock()
    mock_instance.login.side_effect = [Exception("token invalid"), None]
    with patch("garmin.client.garminconnect") as mock_gc:
        mock_gc.Garmin.return_value = mock_instance
        client.connect()
    assert mock_instance.login.call_count == 2
    mock_instance.garth.dump.assert_called_once_with(token_dir)


def test_connect_no_password_uses_token_only(client_no_password, token_dir):
    mock_instance = MagicMock()
    with patch("garmin.client.garminconnect") as mock_gc:
        mock_gc.Garmin.return_value = mock_instance
        client_no_password.connect()
    mock_instance.login.assert_called_once_with(token_dir)


# ── save_token() ─────────────────────────────────────────────────────────────


def test_save_token_calls_garth_dump(client, token_dir):
    mock_instance = MagicMock()
    client._client = mock_instance
    client.save_token()
    mock_instance.garth.dump.assert_called_once_with(token_dir)


def test_save_token_skips_when_client_is_none(client):
    client._client = None
    client.save_token()  # must not raise


def test_save_token_skips_when_garth_attr_missing(client):
    client._client = MagicMock(
        spec=[]
    )  # no attributes → hasattr(..., "garth") is False
    client.save_token()  # must not raise


# ── get_*() — None-to-Default ────────────────────────────────────────────────


def test_get_activities_returns_api_result(client):
    client._client = MagicMock()
    client._client.get_activities_by_date.return_value = [{"activityId": 1}]
    assert client.get_activities(date(2026, 1, 1), date(2026, 1, 7)) == [
        {"activityId": 1}
    ]


def test_get_activities_returns_empty_list_when_none(client):
    client._client = MagicMock()
    client._client.get_activities_by_date.return_value = None
    assert client.get_activities(date(2026, 1, 1), date(2026, 1, 7)) == []


def test_get_daily_summary_returns_empty_dict_when_none(client):
    client._client = MagicMock()
    client._client.get_stats.return_value = None
    assert client.get_daily_summary(date(2026, 1, 1)) == {}


def test_get_sleep_returns_empty_dict_when_none(client):
    client._client = MagicMock()
    client._client.get_sleep_data.return_value = None
    assert client.get_sleep(date(2026, 1, 1)) == {}


def test_get_hrv_returns_empty_dict_when_none(client):
    client._client = MagicMock()
    client._client.get_hrv_data.return_value = None
    assert client.get_hrv(date(2026, 1, 1)) == {}


def test_get_body_battery_returns_empty_list_when_none(client):
    client._client = MagicMock()
    client._client.get_body_battery.return_value = None
    assert client.get_body_battery(date(2026, 1, 1)) == []


def test_get_activity_details_returns_api_result(client):
    client._client = MagicMock()
    client._client.get_activity_details.return_value = {"steps": []}
    assert client.get_activity_details(123) == {"steps": []}


def test_get_activity_details_returns_empty_dict_when_none(client):
    client._client = MagicMock()
    client._client.get_activity_details.return_value = None
    assert client.get_activity_details(123) == {}


def test_get_stress_returns_empty_dict_when_none(client):
    client._client = MagicMock()
    client._client.get_stress_data.return_value = None
    assert client.get_stress(date(2026, 1, 1)) == {}


def test_get_training_status_returns_empty_dict_when_none(client):
    client._client = MagicMock()
    client._client.get_training_status.return_value = None
    assert client.get_training_status(date(2026, 1, 1)) == {}
