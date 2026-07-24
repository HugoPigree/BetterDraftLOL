"""Tests meta status / patch detection."""

from __future__ import annotations

from data_refresh.constants import DEFAULT_ORACLE_CSV
from data_refresh.patches import detect_patch_info, format_patch_label
from meta_status import get_meta_status


def test_format_patch_label() -> None:
    assert format_patch_label(16.13) == "16.13"
    assert format_patch_label(16.1) == "16.1"


def test_detect_patch_info_from_local_oracle() -> None:
    if not DEFAULT_ORACLE_CSV.exists():
        return
    info = detect_patch_info(DEFAULT_ORACLE_CSV)
    assert info["latest_patch"]
    assert isinstance(info["patches"], list)
    assert info["player_rows"] > 0


def test_get_meta_status_returns_latest_patch() -> None:
    status = get_meta_status()
    assert status["latest_patch"]
    assert "patches_available" in status
