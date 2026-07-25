from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from data_refresh.constants import DDRAGON_CACHE_PATH, DDRAGON_META_PATH

logger = logging.getLogger(__name__)

VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"


def fetch_latest_ddragon_version(timeout: int = 30) -> str:
    response = requests.get(VERSIONS_URL, timeout=timeout)
    response.raise_for_status()
    versions = response.json()
    if not versions:
        raise RuntimeError("Aucune version Data Dragon disponible")
    return str(versions[0])


def fetch_ddragon_champions(version: str | None = None, timeout: int = 60) -> tuple[dict[str, Any], str]:
    resolved_version = version or fetch_latest_ddragon_version(timeout=timeout)
    url = f"https://ddragon.leagueoflegends.com/cdn/{resolved_version}/data/en_US/champion.json"
    logger.info("Téléchargement Data Dragon: %s", url)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Format champion.json Data Dragon inattendu")
    return data, resolved_version


def refresh_ddragon_champions(
    cache_path: Path = DDRAGON_CACHE_PATH,
    version: str | None = None,
) -> dict[str, object]:
    """Télécharge champion.json et le met en cache."""
    champions, resolved_version = fetch_ddragon_champions(version=version)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(champions, indent=2), encoding="utf-8")
    DDRAGON_META_PATH.write_text(
        json.dumps({"version": resolved_version, "updated_at": datetime.now(timezone.utc).isoformat()}, indent=2),
        encoding="utf-8",
    )
    return {
        "status": "downloaded",
        "champion_count": len(champions),
        "version": resolved_version,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "cache_path": str(cache_path),
    }


def load_ddragon_champions(cache_path: Path = DDRAGON_CACHE_PATH) -> dict[str, Any]:
    if not cache_path.exists():
        refresh_ddragon_champions(cache_path)
    return json.loads(cache_path.read_text(encoding="utf-8"))
