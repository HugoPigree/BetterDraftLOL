from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

from data_refresh.constants import MERAKI_CACHE_PATH, MERAKI_URL

logger = logging.getLogger(__name__)


def refresh_meraki_champions(
    cache_path: Path = MERAKI_CACHE_PATH,
    url: str = MERAKI_URL,
) -> dict[str, object]:
    """Télécharge le catalogue Meraki (nouveaux champions + rôles)."""
    logger.info("Refresh Meraki: %s", url)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    champions = response.json()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(champions, indent=2), encoding="utf-8")
    return {
        "status": "downloaded",
        "champion_count": len(champions),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "cache_path": str(cache_path),
    }
