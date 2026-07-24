from __future__ import annotations

from pathlib import Path

DATA_DIR = Path("data")
ORACLE_DRIVE_FOLDER_ID = "1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH"
ORACLE_FILENAME_TEMPLATE = "{year}_LoL_esports_match_data_from_OraclesElixir.csv"
DEFAULT_ORACLE_CSV = DATA_DIR / "2026_LoL_esports_match_data_from_OraclesElixir.csv"
ORACLE_DRIVE_INDEX_PATH = DATA_DIR / "oracle_drive_index.json"
MERAKI_URL = "http://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions.json"
MERAKI_CACHE_PATH = DATA_DIR / "meraki_champions.json"
DATA_MANIFEST_PATH = DATA_DIR / "data_manifest.json"
UNMAPPED_CHAMPIONS_PATH = DATA_DIR / "unmapped_champions.txt"

# Fallback si listing Drive indisponible (mis à jour 2026-07-24).
ORACLE_DRIVE_FILE_IDS: dict[str, str] = {
    "2026_LoL_esports_match_data_from_OraclesElixir.csv": "1hnpbrUpBMS1TZI7IovfpKeZfWJH1Aptm",
    "2025_LoL_esports_match_data_from_OraclesElixir.csv": "1v6LRphp2kYciU4SXp0PCjEMuev1bDejc",
}
