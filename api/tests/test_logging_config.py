"""Unit tests for logging_config._release() — version-resolution fallbacks."""

import importlib.metadata
from unittest.mock import patch

from src.logging_config import _release


def test_release_prefers_app_version_env(monkeypatch):
    """APP_VERSION env override wins (line 17)."""
    monkeypatch.setenv("APP_VERSION", "9.9.9")
    assert _release() == "9.9.9"


def test_release_falls_back_to_unknown(monkeypatch):
    """No env, no installed dist, unreadable pyproject → 'unknown' (lines 29-30)."""
    monkeypatch.delenv("APP_VERSION", raising=False)
    with (
        patch(
            "importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError,
        ),
        patch("pathlib.Path.read_text", side_effect=OSError("boom")),
    ):
        assert _release() == "unknown"
