import base64
import json
from pathlib import Path

from cryptography.fernet import Fernet


def fernet_encrypt(data: bytes, key: str) -> bytes:
    return Fernet(key.encode()).encrypt(data)


def fernet_decrypt(data: bytes, key: str) -> bytes:
    return Fernet(key.encode()).decrypt(data)


def serialize_token_dir(token_dir: str) -> bytes:
    """Read all files in token_dir into a JSON blob. Filename-agnostic."""
    files: dict[str, str] = {}
    for f in Path(token_dir).glob("*"):
        if f.is_file():
            files[f.name] = base64.b64encode(f.read_bytes()).decode()
    return json.dumps(files).encode()


def restore_token_dir(data: bytes, token_dir: str) -> None:
    """Write files from a serialized JSON blob back into token_dir."""
    Path(token_dir).mkdir(parents=True, exist_ok=True)
    for name, b64 in json.loads(data).items():
        safe_name = Path(name).name
        if not safe_name or safe_name != name:
            continue
        Path(token_dir, safe_name).write_bytes(base64.b64decode(b64))
