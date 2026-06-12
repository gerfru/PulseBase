import hashlib
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def write_hash(model_path: Path) -> str:
    """Compute SHA-256 of model file and write a sidecar .sha256 file next to it."""
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    model_path.with_suffix(".joblib.sha256").write_text(digest)
    return digest


def verify_and_load(model_path: Path) -> Any:
    """Verify SHA-256 sidecar before joblib.load.

    Raises ValueError if the sidecar exists but the digest does not match —
    this indicates file tampering (CWE-502 mitigation).
    Logs a warning and proceeds if no sidecar exists (backward compatibility
    with models trained before this check was introduced).
    """
    import joblib  # type: ignore[import-untyped]

    hash_path = model_path.with_suffix(".joblib.sha256")
    if hash_path.exists():
        expected = hash_path.read_text().strip()
        actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(
                f"Model integrity check failed for {model_path.name}: "
                f"expected {expected[:16]}…, got {actual[:16]}…"
            )
        logger.info("model.integrity_ok", path=model_path.name)
    else:
        logger.warning("model.integrity_sidecar_missing", path=model_path.name)

    return joblib.load(model_path)
