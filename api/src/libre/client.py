import json
from pathlib import Path

from pylibrelinkup import PyLibreLinkUp


class LibreAuthError(Exception):
    pass


def _token_path(token_dir: str) -> Path:
    return Path(token_dir) / "libre_token.json"


def authenticate(email: str, password: str, token_dir: str) -> PyLibreLinkUp:
    try:
        client = PyLibreLinkUp(email=email, password=password)
        client.authenticate()
    except Exception as e:
        raise LibreAuthError(f"Authentication failed: {e}") from e

    path = _token_path(token_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"token": client.token}))
    return client
