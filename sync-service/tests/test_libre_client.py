"""Tests for sync-service libre/client.py — no real LibreLinkUp API calls."""

import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from libre.client import (
    LibreAuthError,
    authenticate,
    connect,
    connect_with_token,
    get_recent_glucose,
)

_TOKEN_FILE = "libre_token.json"


def test_connect_with_token_sets_token_on_client():
    mock_instance = MagicMock()
    with patch("libre.client.PyLibreLinkUp", return_value=mock_instance):
        client = connect_with_token("test-token-abc123")
    assert client is mock_instance
    assert mock_instance.token == "test-token-abc123"


def test_connect_reads_token_from_file(tmp_path):
    (tmp_path / _TOKEN_FILE).write_text(
        json.dumps({"token": "saved-token", "saved_at": "2026-01-01T00:00:00+00:00"})
    )
    mock_instance = MagicMock()
    with patch("libre.client.PyLibreLinkUp", return_value=mock_instance):
        client = connect(str(tmp_path))
    assert client is mock_instance
    assert mock_instance.token == "saved-token"


def test_connect_raises_when_token_file_missing(tmp_path):
    with pytest.raises(LibreAuthError, match="Kein Token"):
        connect(str(tmp_path))


def test_connect_raises_on_invalid_json(tmp_path):
    (tmp_path / _TOKEN_FILE).write_text("{{not valid json")
    with pytest.raises(Exception):
        connect(str(tmp_path))


def test_authenticate_saves_token_file_and_returns_client(tmp_path):
    mock_instance = MagicMock()
    mock_instance.token = "fresh-token"
    with patch("libre.client.PyLibreLinkUp", return_value=mock_instance):
        result = authenticate("user@example.com", "pass123", str(tmp_path))
    assert result is mock_instance
    token_file = tmp_path / _TOKEN_FILE
    assert token_file.exists()
    data = json.loads(token_file.read_text())
    assert data["token"] == "fresh-token"
    assert "saved_at" in data


def test_authenticate_raises_libre_auth_error_on_failure(tmp_path):
    mock_instance = MagicMock()
    mock_instance.authenticate.side_effect = Exception("invalid credentials")
    with patch("libre.client.PyLibreLinkUp", return_value=mock_instance):
        with pytest.raises(LibreAuthError):
            authenticate("user@example.com", "wrong-password", str(tmp_path))


def test_get_recent_glucose_returns_readings_within_window():
    now = datetime.now(timezone.utc)
    recent = MagicMock()
    recent.timestamp = now - timedelta(minutes=30)  # within 2h window
    old = MagicMock()
    old.timestamp = now - timedelta(hours=3)  # outside 2h window

    graph = MagicMock()
    graph.history = [recent, old]
    graph.current = None

    mock_client = MagicMock()
    mock_client.get_patients.return_value = [MagicMock()]
    mock_client.read.return_value = graph

    readings = get_recent_glucose(mock_client, hours=2)
    assert recent in readings
    assert old not in readings


def test_get_recent_glucose_includes_current_reading():
    now = datetime.now(timezone.utc)
    current = MagicMock()
    current.timestamp = now - timedelta(minutes=5)

    graph = MagicMock()
    graph.history = []
    graph.current = current

    mock_client = MagicMock()
    mock_client.get_patients.return_value = [MagicMock()]
    mock_client.read.return_value = graph

    readings = get_recent_glucose(mock_client, hours=2)
    assert current in readings


def test_get_recent_glucose_returns_empty_for_no_patients():
    mock_client = MagicMock()
    mock_client.get_patients.return_value = []
    assert get_recent_glucose(mock_client, hours=2) == []


def test_get_recent_glucose_raises_on_api_error():
    mock_client = MagicMock()
    mock_client.get_patients.side_effect = Exception("API timeout")
    with pytest.raises(LibreAuthError, match="Libre API-Fehler"):
        get_recent_glucose(mock_client, hours=2)


def test_get_recent_glucose_handles_naive_timestamp():
    now = datetime.now(timezone.utc)
    reading = MagicMock()
    reading.timestamp = (now - timedelta(minutes=10)).replace(tzinfo=None)  # naive

    graph = MagicMock()
    graph.history = [reading]
    graph.current = None

    mock_client = MagicMock()
    mock_client.get_patients.return_value = [MagicMock()]
    mock_client.read.return_value = graph

    readings = get_recent_glucose(mock_client, hours=2)
    assert reading in readings
