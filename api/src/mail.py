import resend as resend_client
import resend.exceptions as resend_exc
import structlog

from src.deps import settings

logger = structlog.get_logger(__name__)


async def _send_email(to: str, subject: str, html: str, log_key: str) -> bool:
    if not settings.resend_api_key:
        logger.warning(
            "mail.send_skipped", log_key=log_key, reason="RESEND_API_KEY not set"
        )
        return False
    resend_client.api_key = settings.resend_api_key
    try:
        resend_client.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": to,
                "subject": subject,
                "html": html,
            }
        )
        return True
    except resend_exc.ResendError as e:
        logger.warning("mail.send_failed", log_key=log_key, reason=e.message)
        return False
    except Exception:
        logger.exception("mail.send_error", log_key=log_key)
        return False


async def send_lockout_email(to_email: str, lockout_minutes: int) -> bool:
    return await _send_email(
        to=to_email,
        subject="PulseBase — Konto vorübergehend gesperrt",
        html=(
            "<p>Dein Konto wurde nach mehreren fehlgeschlagenen Login-Versuchen "
            f"für {lockout_minutes} Minuten gesperrt.</p>"
            "<p>Falls du das nicht warst, ändere bitte dein Passwort über "
            f"<a href='{settings.app_base_url}/auth/reset-request'>"
            "Passwort zurücksetzen</a>.</p>"
        ),
        log_key="lockout",
    )


async def send_reset_email(to_email: str, token: str) -> bool:
    url = f"{settings.app_base_url}/auth/reset/{token}"
    return await _send_email(
        to=to_email,
        subject="PulseBase — Passwort zurücksetzen",
        html=(
            f"<p>Klicke auf diesen Link um dein Passwort zurückzusetzen "
            f"(gültig 1 Stunde):</p><p><a href='{url}'>{url}</a></p>"
        ),
        log_key="reset",
    )


async def send_verify_email(to_email: str, token: str) -> bool:
    url = f"{settings.app_base_url}/auth/verify/{token}"
    return await _send_email(
        to=to_email,
        subject="PulseBase — E-Mail-Adresse bestätigen",
        html=(
            "<p>Klicke auf diesen Link um deine E-Mail-Adresse zu bestätigen "
            f"(gültig 24 Stunden):</p><p><a href='{url}'>{url}</a></p>"
        ),
        log_key="verify",
    )


async def send_deletion_confirm_email(to_email: str, token: str) -> bool:
    url = f"{settings.app_base_url}/account/delete/confirm/{token}"
    return await _send_email(
        to=to_email,
        subject="PulseBase — Kontolöschung bestätigen",
        html=(
            "<p>Du hast die Löschung deines Kontos angefordert.</p>"
            "<p>Klicke auf diesen Link um die Löschung zu bestätigen "
            f"(gültig 24 Stunden):</p><p><a href='{url}'>{url}</a></p>"
            "<p>Falls du das nicht warst, kannst du diesen Link ignorieren. "
            "Dein Konto bleibt unverändert.</p>"
        ),
        log_key="deletion_confirm",
    )
