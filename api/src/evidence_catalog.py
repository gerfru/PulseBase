import json
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "data" / "evidence_catalog.json"
EVIDENCE: dict[str, dict] = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
