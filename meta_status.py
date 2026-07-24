"""Expose l'état des données pro pour l'API et le frontend."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_refresh.constants import (
    DATA_MANIFEST_PATH,
    DEFAULT_ORACLE_CSV,
    MERAKI_CACHE_PATH,
)
from data_refresh.manifest import load_data_manifest
from data_refresh.patches import detect_patch_info


def _file_mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def get_meta_status() -> dict[str, Any]:
    manifest = load_data_manifest(DATA_MANIFEST_PATH)
    patch_info = manifest.get("patches") if manifest else None

    if not patch_info:
        try:
            patch_info = detect_patch_info(DEFAULT_ORACLE_CSV)
        except Exception:
            patch_info = {"latest_patch": "16.13", "patches": [], "player_rows": 0}

    oracle_section = manifest.get("oracle") if manifest else {}
    meraki_section = manifest.get("meraki") if manifest else {}
    unmapped = manifest.get("unmapped_champions") if manifest else []

    latest_patch = str(patch_info.get("latest_patch") or "16.13")
    built_at = manifest.get("built_at") or _file_mtime_iso(DATA_MANIFEST_PATH)

    return {
        "latest_patch": latest_patch,
        "patches_available": patch_info.get("patches") or [],
        "data_built_at": built_at,
        "oracle_updated_at": oracle_section.get("downloaded_at") or _file_mtime_iso(DEFAULT_ORACLE_CSV),
        "oracle_status": oracle_section.get("status") or ("local" if DEFAULT_ORACLE_CSV.exists() else "missing"),
        "oracle_team_games": patch_info.get("team_games"),
        "meraki_updated_at": meraki_section.get("updated_at") or _file_mtime_iso(MERAKI_CACHE_PATH),
        "meraki_champion_count": meraki_section.get("champion_count"),
        "unmapped_champions": unmapped or [],
        "schema_version": manifest.get("schema_version", 0),
    }
