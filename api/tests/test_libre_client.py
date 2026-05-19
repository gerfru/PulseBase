"""Unit tests for libre.client — mocks PyLibreLinkUp."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.libre.client import LibreAuthError, _token_path, authenticate


def test_token_path_returns_correct_path():
    p = _token_path("/app/tokens/1")
    assert p == Path("/app/tokens/1/libre_token.json")


def test_authenticate_success_writes_token_and_returns_client(tmp_path):
    mock_client = MagicMock()
    mock_client.token = "libre-token-abc"

    with patch("src.libre.client.PyLibreLinkUp", return_value=mock_client):
        result = authenticate(
            "user@libre.com", "pass123", str(tmp_path)
        )  # pragma: allowlist secret

    assert result is mock_client
    mock_client.authenticate.assert_called_once()

    token_file = tmp_path / "libre_token.json"
    assert token_file.exists()
    assert json.loads(token_file.read_text())["token"] == "libre-token-abc"


def test_authenticate_raises_libre_auth_error_on_failure(tmp_path):
    mock_client = MagicMock()
    mock_client.authenticate.side_effect = Exception("invalid credentials")

    with patch("src.libre.client.PyLibreLinkUp", return_value=mock_client):
        with pytest.raises(LibreAuthError):
            authenticate(
                "user@libre.com", "wrong", str(tmp_path)
            )  # pragma: allowlist secret
