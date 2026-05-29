import ipaddress
import time
from pathlib import Path

import bcrypt
import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from src.db import Settings, get_user_by_id

logger = structlog.get_logger(__name__)

settings = Settings()  # type: ignore[call-arg]

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


limiter = Limiter(key_func=_get_real_ip)

DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "RATE_LIMITED", "message": "Too many requests."}},
    )


class NeedsLogin(Exception):
    pass


async def require_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise NeedsLogin()
    user = await get_user_by_id(int(user_id))
    if not user:
        raise NeedsLogin()
    return user


templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["v"] = str(int(time.time()))
