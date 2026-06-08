import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.db import get_reset_token_user_id, save_reset_token
from src.deps import settings

_RESET_SALT = "password-reset"
_RESET_MAX_AGE = 900  # 15 min (OWASP: short-lived one-time reset token)
_VERIFY_SALT = "email-verify"
_VERIFY_MAX_AGE = 86400  # 24 hours
_DELETION_SALT = "account-delete"
_DELETION_MAX_AGE = 86400  # 24 hours


async def _make_reset_token(user_id: int) -> str:
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_RESET_MAX_AGE)
    await save_reset_token(user_id, token_hash, expires_at)
    return raw


async def _verify_reset_token(token: str) -> int | None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return await get_reset_token_user_id(token_hash)


def _make_verify_token(user_id: int) -> str:
    return URLSafeTimedSerializer(settings.session_secret).dumps(
        user_id, salt=_VERIFY_SALT
    )


def _verify_email_token(token: str) -> int | None:
    try:
        user_id = URLSafeTimedSerializer(settings.session_secret).loads(
            token, salt=_VERIFY_SALT, max_age=_VERIFY_MAX_AGE
        )
        return int(user_id)
    except (BadSignature, SignatureExpired):
        return None


def _make_deletion_token(user_id: int) -> str:
    return URLSafeTimedSerializer(settings.session_secret).dumps(
        user_id, salt=_DELETION_SALT
    )


def _verify_deletion_token(token: str) -> int | None:
    try:
        user_id = URLSafeTimedSerializer(settings.session_secret).loads(
            token, salt=_DELETION_SALT, max_age=_DELETION_MAX_AGE
        )
        return int(user_id)
    except (BadSignature, SignatureExpired):
        return None
