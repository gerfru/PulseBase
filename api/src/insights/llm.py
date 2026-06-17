"""LLM-Provider fuer KI-Wochen-Insights (ADR-0003, Schicht 2).

Lokales Ollama, das NATIV am Host laeuft (nicht in Docker — Metal-GPU). Der
``api``-Container spricht es per URL an. Default ist aus (``ollama_enabled``);
dann liefert die Orchestrierung das deterministische Fallback.

Health-Payload (der Prompt) geht nur an das lokale Modell und wird NIE geloggt
(Security-Design C3) — nur Metadaten (Modell, Latenz, Zeichenzahl).
"""

from __future__ import annotations

import time
from typing import Protocol

import httpx
import structlog

from src.db.pool import Settings
from src.db.pool import settings as _settings

logger = structlog.get_logger(__name__)


class LlmProvider(Protocol):
    model: str

    async def complete(self, prompt: str) -> str: ...


class OllamaProvider:
    """httpx-Client gegen die native Ollama-Instanz (``/api/generate``)."""

    def __init__(self, base_url: str, model: str, timeout_seconds: int) -> None:
        self._base_url = base_url.rstrip("/")
        self.model = model
        self._timeout = timeout_seconds

    async def complete(self, prompt: str) -> str:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            text = str(resp.json().get("response", ""))
        logger.info(
            "insights.ollama.complete",
            model=self.model,
            latency_ms=round((time.monotonic() - start) * 1000),
            chars=len(text),  # Metadaten — kein Payload
        )
        return text


def get_provider(settings: Settings = _settings) -> LlmProvider | None:
    """Liefert den konfigurierten Provider oder ``None`` (Generierung deaktiviert)."""
    if not settings.ollama_enabled:
        return None
    return OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
