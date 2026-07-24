#!/usr/bin/env python3
"""Orchestre le refresh quotidien : Oracle Drive → Meraki → datasets dérivés."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_refresh.constants import (
    DATA_DIR,
    DATA_MANIFEST_PATH,
    DEFAULT_ORACLE_CSV,
    MERAKI_CACHE_PATH,
    UNMAPPED_CHAMPIONS_PATH,
)
from data_refresh.manifest import build_manifest, write_data_manifest
from data_refresh.meraki import refresh_meraki_champions
from data_refresh.oracle import fetch_oracle_csv
from data_refresh.patches import detect_patch_info

logger = logging.getLogger(__name__)


def _run_step(label: str, command: list[str]) -> None:
    logger.info("=== %s ===", label)
    subprocess.run(command, cwd=ROOT, check=True)


def _read_unmapped() -> list[str]:
    if not UNMAPPED_CHAMPIONS_PATH.exists():
        return []
    lines = UNMAPPED_CHAMPIONS_PATH.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def refresh_all(
    *,
    skip_download: bool = False,
    skip_training_dataset: bool = False,
    train_model: bool = False,
) -> dict[str, object]:
    oracle_result: dict[str, object] = {"status": "skipped_download"}
    if not skip_download:
        oracle_result = fetch_oracle_csv(DEFAULT_ORACLE_CSV)
    elif DEFAULT_ORACLE_CSV.exists():
        from datetime import datetime, timezone

        stat = DEFAULT_ORACLE_CSV.stat()
        oracle_result = {
            "status": "skipped_download",
            "filename": DEFAULT_ORACLE_CSV.name,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "downloaded_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }

    meraki_result = refresh_meraki_champions(MERAKI_CACHE_PATH)

    _run_step("Duo datasets", [sys.executable, "build_duo_dataset.py"])
    _run_step("Meta tierlist", [sys.executable, "build_meta_tierlist.py"])
    if not skip_training_dataset:
        _run_step("Training dataset", [sys.executable, "build_training_dataset.py"])
    if train_model:
        _run_step("Synergy model", [sys.executable, "train_synergy_model.py"])

    patch_info = detect_patch_info(DEFAULT_ORACLE_CSV)
    unmapped = _read_unmapped()

    manifest = build_manifest(
        oracle=oracle_result,
        meraki=meraki_result,
        patches=patch_info,
        unmapped_champions=unmapped,
        artifacts={
            "oracle_csv": str(DEFAULT_ORACLE_CSV),
            "meta_tierlist": str(DATA_DIR / "meta_tierlist.csv"),
            "duo_bot_lane": str(DATA_DIR / "duo_bot_lane.csv"),
            "duo_jungle_support": str(DATA_DIR / "duo_jungle_support.csv"),
            "meraki_cache": str(MERAKI_CACHE_PATH),
        },
        warnings=(
            ["unmapped_champions_detected"] if unmapped else []
        ),
    )
    write_data_manifest(manifest, DATA_MANIFEST_PATH)
    logger.info("Manifest écrit: %s", DATA_MANIFEST_PATH)
    logger.info("Patch pro le plus récent: %s", patch_info.get("latest_patch"))
    if unmapped:
        logger.warning("Champions non mappés Meraki: %s", ", ".join(unmapped[:10]))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh data pro BetterDraftLOL")
    parser.add_argument("--skip-download", action="store_true", help="Rebuild sans re-télécharger Oracle")
    parser.add_argument("--skip-training-dataset", action="store_true")
    parser.add_argument("--train-model", action="store_true", help="Réentraîner XGBoost (hebdo)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    started = datetime.now(timezone.utc)
    try:
        refresh_all(
            skip_download=args.skip_download,
            skip_training_dataset=args.skip_training_dataset,
            train_model=args.train_model,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Échec pipeline refresh (code %s)", exc.returncode)
        sys.exit(exc.returncode or 1)
    except Exception as exc:
        logger.exception("Refresh interrompu: %s", exc)
        sys.exit(1)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    logger.info("Refresh terminé en %.1f s", elapsed)


if __name__ == "__main__":
    main()
