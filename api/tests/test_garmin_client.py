"""Unit tests for GarminClient — mocks garminconnect.Garmin entirely."""

from datetime import date
from unittest.mock import MagicMock, patch

from src.garmin.client import GarminClient


def _connected_client(mock_garmin_instance, tmp_path):
    """Return a GarminClient whose connect() succeeded via token login."""
    with patch("garminconnect.Garmin", return_value=mock_garmin_instance):
        mock_garmin_instance.login.return_value = None
        client = GarminClient("test@example.com", "pass", str(tmp_path))
        client.connect()
    return client


def test_connect_token_login_succeeds(tmp_path):
    mock = MagicMock()
    mock.login.return_value = None
    with patch("garminconnect.Garmin", return_value=mock):
        client = GarminClient("u@example.com", "p", str(tmp_path))
        client.connect()
    mock.login.assert_called_once_with(str(tmp_path))
    mock.garth.dump.assert_not_called()


def test_connect_falls_back_to_fresh_login_on_token_failure(tmp_path):
    mock = MagicMock()
    mock.login.side_effect = [Exception("token expired"), None]
    with patch("garminconnect.Garmin", return_value=mock):
        client = GarminClient("u@example.com", "p", str(tmp_path))
        client.connect()
    assert mock.login.call_count == 2
    mock.garth.dump.assert_called_once_with(str(tmp_path))


def test_get_activities_returns_list(tmp_path):
    mock = MagicMock()
    mock.login.return_value = None
    mock.get_activities_by_date.return_value = [{"activityId": 42}]
    client = _connected_client(mock, tmp_path)
    result = client.get_activities(date(2026, 1, 1), date(2026, 1, 7))
    assert result == [{"activityId": 42}]
    mock.get_activities_by_date.assert_called_once_with("2026-01-01", "2026-01-07")


def test_get_activities_returns_empty_list_when_none(tmp_path):
    mock = MagicMock()
    mock.login.return_value = None
    mock.get_activities_by_date.return_value = None
    client = _connected_client(mock, tmp_path)
    assert client.get_activities(date(2026, 1, 1), date(2026, 1, 7)) == []


def test_get_activity_details(tmp_path):
    mock = MagicMock()
    mock.login.return_value = None
    mock.get_activity_details.return_value = {"summary": {"activityId": 99}}
    client = _connected_client(mock, tmp_path)
    assert client.get_activity_details(99) == {"summary": {"activityId": 99}}
    mock.get_activity_details.assert_called_once_with(99)


def test_get_daily_summary(tmp_path):
    mock = MagicMock()
    mock.login.return_value = None
    mock.get_stats.return_value = {"totalSteps": 8000}
    client = _connected_client(mock, tmp_path)
    assert client.get_daily_summary(date(2026, 5, 1)) == {"totalSteps": 8000}
    mock.get_stats.assert_called_once_with("2026-05-01")


def test_get_sleep(tmp_path):
    mock = MagicMock()
    mock.login.return_value = None
    mock.get_sleep_data.return_value = {"sleepScore": 75}
    client = _connected_client(mock, tmp_path)
    assert client.get_sleep(date(2026, 5, 1)) == {"sleepScore": 75}


def test_get_hrv(tmp_path):
    mock = MagicMock()
    mock.login.return_value = None
    mock.get_hrv_data.return_value = {"weeklyAvg": 45}
    client = _connected_client(mock, tmp_path)
    assert client.get_hrv(date(2026, 5, 1)) == {"weeklyAvg": 45}


def test_get_body_battery(tmp_path):
    mock = MagicMock()
    mock.login.return_value = None
    mock.get_body_battery.return_value = [{"charged": 80}]
    client = _connected_client(mock, tmp_path)
    result = client.get_body_battery(date(2026, 5, 1))
    assert result == [{"charged": 80}]
    mock.get_body_battery.assert_called_once_with("2026-05-01", "2026-05-01")


def test_get_stress(tmp_path):
    mock = MagicMock()
    mock.login.return_value = None
    mock.get_stress_data.return_value = {"avgStressLevel": 30}
    client = _connected_client(mock, tmp_path)
    assert client.get_stress(date(2026, 5, 1)) == {"avgStressLevel": 30}
