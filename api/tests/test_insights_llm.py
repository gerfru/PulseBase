"""Tests fuer den LLM-Provider (gemocktes httpx, kein echtes Modell)."""

from types import SimpleNamespace

import httpx
import pytest

from src.insights.llm import OllamaProvider, get_provider


class _Resp:
    def __init__(self, data: dict) -> None:
        self._d = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._d


class _Client:
    def __init__(self, *, resp: _Resp | None = None, exc: Exception | None = None):
        self._resp, self._exc = resp, exc

    async def __aenter__(self) -> "_Client":
        return self

    async def __aexit__(self, *a: object) -> bool:
        return False

    async def post(self, url: str, json: dict | None = None) -> _Resp:
        if self._exc is not None:
            raise self._exc
        assert self._resp is not None
        return self._resp


async def test_ollama_complete_returns_response(monkeypatch):
    client = _Client(resp=_Resp({"response": "Hallo Welt"}))
    monkeypatch.setattr("src.insights.llm.httpx.AsyncClient", lambda **kw: client)
    out = await OllamaProvider("http://h:11434", "m", 5).complete("p")
    assert out == "Hallo Welt"


async def test_ollama_complete_propagates_http_error(monkeypatch):
    client = _Client(exc=httpx.ConnectError("boom"))
    monkeypatch.setattr("src.insights.llm.httpx.AsyncClient", lambda **kw: client)
    with pytest.raises(httpx.ConnectError):
        await OllamaProvider("http://h:11434", "m", 5).complete("p")


def _settings(enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        ollama_enabled=enabled,
        ollama_base_url="http://h:11434",
        ollama_model="m",
        ollama_timeout_seconds=5,
    )


def test_get_provider_none_when_disabled():
    assert get_provider(_settings(False)) is None  # type: ignore[arg-type]


def test_get_provider_returns_ollama_when_enabled():
    provider = get_provider(_settings(True))  # type: ignore[arg-type]
    assert provider is not None and provider.model == "m"
