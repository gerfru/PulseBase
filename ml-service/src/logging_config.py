import importlib.metadata
import logging
import os
import sys
from typing import Any

import sentry_sdk
import structlog


def _release() -> str:
    """App version for Sentry release tracking. Single source = pyproject version.
    Resolution: APP_VERSION env override → installed dist metadata (Docker, pip
    install .) → pyproject.toml on disk (dev/uv run from source) → 'unknown'."""
    env = os.environ.get("APP_VERSION")
    if env:
        return env
    for dist in ("pulsebase-api", "pulsebase-sync", "pulsebase-ml"):
        try:
            return importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            continue
    try:
        import tomllib
        from pathlib import Path

        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        return str(tomllib.loads(pyproject.read_text())["project"]["version"])
    except Exception:
        return "unknown"


def _sentry_error_processor(logger: Any, method: str, event_dict: Any) -> Any:
    """Forward ERROR/CRITICAL structlog events to Sentry. No-op when DSN not configured."""
    if method in ("error", "critical"):
        exc_info = event_dict.get("exc_info")
        if exc_info is True:
            sentry_sdk.capture_exception()
        elif exc_info and exc_info is not False:
            sentry_sdk.capture_exception(exc_info)
        else:
            sentry_sdk.capture_message(str(event_dict.get("event", "")), level=method)  # type: ignore[arg-type]
    return event_dict


def configure_logging() -> None:
    """Configure structlog for JSON output with UTC timestamps and stdlib bridge."""
    _level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    _pre: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    structlog.configure(
        processors=[
            *_pre,
            _sentry_error_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_level),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(file=sys.stdout),
    )

    # M-47: route stdlib logs (APScheduler, httpx, …) through JSON pipeline
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=_pre,
            processor=structlog.processors.JSONRenderer(),
        )
    )
    _root = logging.getLogger()
    _root.handlers.clear()
    _root.addHandler(_handler)
    _root.setLevel(_level)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def configure_sentry(settings: Any, integrations: list[Any] | None = None) -> None:
    """Initialize Sentry SDK from settings.sentry_dsn. No-op when DSN is not set."""
    dsn = getattr(settings, "sentry_dsn", None)
    _log = structlog.get_logger(__name__)
    if not dsn:
        _log.warning("sentry.disabled", reason="SENTRY_DSN not configured")
        return
    sentry_sdk.init(
        dsn=dsn,
        send_default_pii=False,
        traces_sample_rate=0.1,
        environment=os.environ.get("APP_ENV", "production"),
        release=_release(),
        integrations=integrations or [],
    )
    _log.info("sentry.initialized")
