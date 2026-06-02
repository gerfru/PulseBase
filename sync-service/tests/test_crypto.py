"""Tests for sync-service src/crypto.py — Fernet encrypt/decrypt + token dir serialization."""

import base64
import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken

from crypto import (
    fernet_decrypt,
    fernet_encrypt,
    restore_token_dir,
    serialize_token_dir,
)


@pytest.fixture
def fernet_key() -> str:
    return Fernet.generate_key().decode()


# ── fernet_encrypt / fernet_decrypt ─────────────────────────────────────────


def test_fernet_encrypt_decrypt_roundtrip(fernet_key: str) -> None:
    plaintext = b"secret token data"
    assert (
        fernet_decrypt(fernet_encrypt(plaintext, fernet_key), fernet_key) == plaintext
    )


def test_fernet_decrypt_with_wrong_key_raises(fernet_key: str) -> None:
    other_key = Fernet.generate_key().decode()
    encrypted = fernet_encrypt(b"data", fernet_key)
    with pytest.raises(InvalidToken):
        fernet_decrypt(encrypted, other_key)


# ── serialize_token_dir ──────────────────────────────────────────────────────


def test_serialize_token_dir_single_file(tmp_path: Path) -> None:
    (tmp_path / "oauth2_token.json").write_bytes(b'{"token":"abc"}')
    blob = serialize_token_dir(str(tmp_path))
    data = json.loads(blob)
    assert list(data.keys()) == ["oauth2_token.json"]


def test_serialize_token_dir_multiple_files(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_bytes(b"aaa")
    (tmp_path / "b.bin").write_bytes(b"bbb")
    blob = serialize_token_dir(str(tmp_path))
    data = json.loads(blob)
    assert set(data.keys()) == {"a.json", "b.bin"}


def test_serialize_token_dir_empty(tmp_path: Path) -> None:
    blob = serialize_token_dir(str(tmp_path))
    assert json.loads(blob) == {}


def test_serialize_token_dir_ignores_subdirectories(tmp_path: Path) -> None:
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.json").write_bytes(b"nested")
    (tmp_path / "top.json").write_bytes(b"top")
    blob = serialize_token_dir(str(tmp_path))
    data = json.loads(blob)
    assert list(data.keys()) == ["top.json"]


# ── restore_token_dir ────────────────────────────────────────────────────────


def test_restore_token_dir_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "oauth2_token.json").write_bytes(b'{"token":"abc"}')
    (src / "extra.bin").write_bytes(b"\x00\x01\x02")

    blob = serialize_token_dir(str(src))

    dst = tmp_path / "dst"
    restore_token_dir(blob, str(dst))

    assert (dst / "oauth2_token.json").read_bytes() == b'{"token":"abc"}'
    assert (dst / "extra.bin").read_bytes() == b"\x00\x01\x02"


def test_restore_token_dir_path_traversal_blocked(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    blob = json.dumps(
        {
            "../evil.txt": base64.b64encode(b"pwned").decode(),
            "safe.json": base64.b64encode(b"ok").decode(),
        }
    ).encode()

    restore_token_dir(blob, str(target))

    assert not (tmp_path / "evil.txt").exists(), (
        "Path traversal must not write outside target_dir"
    )
    assert (target / "safe.json").read_bytes() == b"ok"


def test_restore_token_dir_absolute_path_blocked(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    blob = json.dumps(
        {"/etc/cron.d/pwned": base64.b64encode(b"evil").decode()}
    ).encode()

    restore_token_dir(blob, str(target))

    assert list(target.iterdir()) == [], "Absolute path entry must be skipped"
