from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from data_refresh.constants import (
    DATA_DIR,
    DEFAULT_ORACLE_CSV,
    ORACLE_DRIVE_FILE_IDS,
    ORACLE_DRIVE_FOLDER_ID,
    ORACLE_DRIVE_INDEX_PATH,
    ORACLE_FILENAME_TEMPLATE,
)

logger = logging.getLogger(__name__)


def refresh_oracle_drive_index(*, force: bool = False) -> dict[str, str]:
    """Liste les fichiers Oracle sur Drive et persiste filename -> file_id."""
    if ORACLE_DRIVE_INDEX_PATH.exists() and not force:
        try:
            cached = json.loads(ORACLE_DRIVE_INDEX_PATH.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and cached.get("files"):
                return dict(cached["files"])
        except (json.JSONDecodeError, KeyError):
            pass

    try:
        import gdown
    except ImportError as exc:
        logger.warning("gdown absent, index Drive par défaut: %s", exc)
        return dict(ORACLE_DRIVE_FILE_IDS)

    try:
        entries = gdown.download_folder(
            id=ORACLE_DRIVE_FOLDER_ID,
            output=str(DATA_DIR / "_drive_listing"),
            quiet=True,
            skip_download=True,
            use_cookies=False,
        )
        index = {entry.path: entry.id for entry in entries}
    except Exception as exc:
        logger.warning("Listing Drive impossible (%s), index embarqué.", exc)
        index = dict(ORACLE_DRIVE_FILE_IDS)
    else:
        merged = dict(ORACLE_DRIVE_FILE_IDS)
        merged.update(index)
        index = merged

    ORACLE_DRIVE_INDEX_PATH.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "files": index,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return index


def _resolve_oracle_filename(year: int | None = None) -> str:
    year = year or datetime.now(timezone.utc).year
    return ORACLE_FILENAME_TEMPLATE.format(year=year)


def _resolve_file_id(filename: str, index: dict[str, str]) -> str | None:
    if filename in index:
        return index[filename]
    return ORACLE_DRIVE_FILE_IDS.get(filename)


def _download_with_gdown(file_id: str, dest: Path) -> None:
    import gdown

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    gdown.download(id=file_id, output=str(tmp), quiet=True, use_cookies=False)
    if not tmp.exists() or tmp.stat().st_size < 1024:
        raise RuntimeError(f"Téléchargement Oracle invalide: {tmp}")
    tmp.replace(dest)


def fetch_oracle_csv(
    dest: Path = DEFAULT_ORACLE_CSV,
    *,
    year: int | None = None,
    retries: int = 3,
    retry_delay_s: float = 8.0,
) -> dict[str, object]:
    """Télécharge le CSV Oracle de l'année courante (fallback année précédente)."""
    index = refresh_oracle_drive_index()
    year = year or datetime.now(timezone.utc).year
    tried_years: list[int] = []
    last_error: str | None = None

    for attempt_year in (year, year - 1):
        if attempt_year in tried_years:
            continue
        tried_years.append(attempt_year)
        filename = _resolve_oracle_filename(attempt_year)
        file_id = _resolve_file_id(filename, index)
        if not file_id:
            last_error = f"ID Drive introuvable pour {filename}"
            continue

        for attempt in range(1, retries + 1):
            try:
                logger.info(
                    "Téléchargement Oracle %s (id=%s, tentative %d/%d)",
                    filename,
                    file_id,
                    attempt,
                    retries,
                )
                _download_with_gdown(file_id, dest)
                size_mb = round(dest.stat().st_size / (1024 * 1024), 2)
                return {
                    "status": "downloaded",
                    "filename": filename,
                    "year": attempt_year,
                    "file_id": file_id,
                    "size_mb": size_mb,
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                }
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Échec download Oracle (%s)", exc)
                if attempt < retries:
                    time.sleep(retry_delay_s * attempt)

    if dest.exists():
        logger.warning(
            "Refresh Oracle impossible (%s) — conservation du fichier local %s",
            last_error,
            dest,
        )
        stat = dest.stat()
        return {
            "status": "skipped_using_local",
            "filename": dest.name,
            "year": year,
            "error": last_error,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "downloaded_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }

    raise RuntimeError(
        f"Impossible de télécharger Oracle ({last_error}) et aucun CSV local: {dest}"
    )
