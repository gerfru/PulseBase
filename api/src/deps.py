import hashlib
import hmac
import ipaddress
import secrets
import time
from datetime import date as Date
from pathlib import Path
from typing import Any, TypedDict, cast

import bcrypt
import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from src.db import get_user_by_id
from src.db.pool import settings

logger = structlog.get_logger(__name__)

_TRUSTED_NETWORKS = [
    ipaddress.ip_network(cidr) for cidr in settings.trusted_proxy_cidrs
]


def _is_trusted_proxy(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _TRUSTED_NETWORKS)
    except ValueError:
        return False


def _get_real_ip(request: Request) -> str:
    client_host = request.client.host if request.client else "127.0.0.1"
    if _is_trusted_proxy(client_host):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return client_host


_IP_HASH_PREFIX_LEN = 12  # enough entropy for log correlation without reversibility


def _ip_hash(request: Request) -> str:
    return hashlib.sha256(_get_real_ip(request).encode()).hexdigest()[
        :_IP_HASH_PREFIX_LEN
    ]


limiter = Limiter(key_func=_get_real_ip)

DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt(rounds=12)).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# Map HTTP status codes to stable, machine-readable error codes for the unified
# error envelope `{error:{code,message,details?}}`. Used by the global exception
# handlers in main.py and the manual JSONResponse error sites in the routers.
HTTP_ERROR_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def error_envelope(
    code: str, message: str, details: Any | None = None
) -> dict[str, dict[str, Any]]:
    """Build the unified error body `{error:{code,message,details?}}`.

    `details` is omitted when None so simple errors stay compact. Never put
    client-submitted values (e.g. a posted password) into `details` — see the
    RequestValidationError handler in main.py, which strips Pydantic's `input`.
    """
    err: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"error": err}


async def _rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=error_envelope("RATE_LIMITED", "Too many requests."),
    )


class UserRow(TypedDict):
    id: int
    name: str
    email: str
    garmin_linked: bool
    garmin_email: str | None
    libre_linked: bool
    libre_email: str | None
    date_of_birth: Date | None
    sex: str | None
    epilepsy_mode: bool
    spo2_enabled: bool


class NeedsLogin(Exception):
    pass


async def require_user(request: Request) -> UserRow:
    user_id = request.session.get("user_id")
    if not user_id:
        raise NeedsLogin()
    user = await get_user_by_id(int(user_id))
    if not user:
        raise NeedsLogin()
    return cast(UserRow, user)


class NonceTemplates(Jinja2Templates):
    def TemplateResponse(  # type: ignore[override]
        self,
        request: Request,
        name: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        ctx = {**(context or {})}
        ctx.setdefault("nonce", getattr(request.state, "nonce", ""))
        return super().TemplateResponse(request, name, ctx, **kwargs)


templates = NonceTemplates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["v"] = str(int(time.time()))


def generate_csrf_token(request: Request) -> str:
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_urlsafe(32)
    return request.session["csrf_token"]


def verify_csrf_token(request: Request, form_token: str | None) -> bool:
    session_token = request.session.get("csrf_token", "")
    if not session_token or not form_token:
        return False
    return hmac.compare_digest(session_token, form_token)
