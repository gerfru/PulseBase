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
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            _sentry_error_processor,
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

    # Bridge: route stdlib logs (uvicorn, httpx, etc.) through structlog's JSON output
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
