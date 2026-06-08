import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from src.db import (
    get_deletion_token_user_id,
    get_reset_token_user_id,
    get_verify_token_user_id,
    save_deletion_token,
    save_reset_token,
    save_verify_token,
)

# All three token types are DB-backed single-use: a random token is e-mailed, only
# its SHA-256 hash + expiry is stored on the user row, verified server-side and
# cleared on use (or removed with the user on deletion). No replayable stateless tokens.
_RESET_MAX_AGE = 900  # 15 min (OWASP: short-lived one-time reset token)
_VERIFY_MAX_AGE = 86400  # 24 hours
_DELETION_MAX_AGE = 3600  # 1 hour — deletion is destructive, keep the window tight


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _make_reset_token(user_id: int) -> str:
    raw = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_RESET_MAX_AGE)
    await save_reset_token(user_id, _hash(raw), expires_at)
    return raw


async def _verify_reset_token(token: str) -> int | None:
    return await get_reset_token_user_id(_hash(token))


async def _make_verify_token(user_id: int) -> str:
    raw = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_VERIFY_MAX_AGE)
    await save_verify_token(user_id, _hash(raw), expires_at)
    return raw


async def _verify_email_token(token: str) -> int | None:
    return await get_verify_token_user_id(_hash(token))


async def _make_deletion_token(user_id: int) -> str:
    raw = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_DELETION_MAX_AGE)
    await save_deletion_token(user_id, _hash(raw), expires_at)
    return raw


async def _verify_deletion_token(token: str) -> int | None:
    return await get_deletion_token_user_id(_hash(token))
