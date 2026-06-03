import logging
import sys
from typing import Any

import sentry_sdk
import structlog


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
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(),
    )

    # M-47: route stdlib logs (uvicorn, httpx, …) through JSON pipeline
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
    _root.setLevel(logging.INFO)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
