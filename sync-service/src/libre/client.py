import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pylibrelinkup import PyLibreLinkUp  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_TOKEN_FILE = "libre_token.json"


class LibreAuthError(Exception):
    pass


def _token_path(token_dir: str) -> Path:
    return Path(token_dir) / _TOKEN_FILE


def authenticate(email: str, password: str, token_dir: str) -> PyLibreLinkUp:
    """First-time auth: email+password → saves token, returns client. Password is not persisted."""
    client = PyLibreLinkUp(email=email, password=password)
    try:
        client.authenticate()
    except Exception as e:
        raise LibreAuthError(
            f"LibreLinkUp-Authentifizierung fehlgeschlagen: {e}"
        ) from e

    path = Path(token_dir)
    path.mkdir(parents=True, exist_ok=True)
    token_data = {
        "token": client.token,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    _token_path(token_dir).write_text(json.dumps(token_data))
    logger.info(f"LibreLinkUp token saved to {token_dir}")
    return client


def connect(token_dir: str) -> PyLibreLinkUp:
    """Restore client from saved token. Raises LibreAuthError if missing or invalid."""
    tp = _token_path(token_dir)
    if not tp.exists():
        raise LibreAuthError("Kein Token gefunden — Neu-Verknüpfung erforderlich")

    data = json.loads(tp.read_text())
    client = PyLibreLinkUp(email="", password="")
    client.token = data["token"]
    return client


def get_recent_glucose(client: PyLibreLinkUp, hours: int = 2) -> list:
    """Fetch glucose readings from all connections for the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    readings: list = []
    try:
        patients = client.get_patients()
        for patient in patients:
            graph = client.read(patient)
            for r in graph.history:
                ts = (
                    r.timestamp
                    if r.timestamp.tzinfo
                    else r.timestamp.replace(tzinfo=timezone.utc)
                )
                if ts >= cutoff:
                    readings.append(r)
            if graph.current:
                ts = graph.current.timestamp
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    readings.append(graph.current)
    except Exception as e:
        raise LibreAuthError(f"Libre API-Fehler (Token abgelaufen?): {e}") from e

    return readings
