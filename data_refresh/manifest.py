from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_refresh.constants import DATA_MANIFEST_PATH


def load_data_manifest(path: Path = DATA_MANIFEST_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def write_data_manifest(payload: dict[str, Any], path: Path = DATA_MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_manifest(**sections: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "built_at": datetime.now(timezone.utc).isoformat(),
        **sections,
    }
