#!/usr/bin/env python3
"""Collect solo queue winrates by champion/role from high-Elo players via Riot API."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import requests

# Platform routing (league-v4, summoner-v4) vs regional routing (match-v5)
REGION_CONFIG: dict[str, dict[str, str]] = {
    "euw": {"platform": "euw1", "regional": "europe"},
    "eune": {"platform": "eun1", "regional": "europe"},
    "na": {"platform": "na1", "regional": "americas"},
    "kr": {"platform": "kr", "regional": "asia"},
    "br": {"platform": "br1", "regional": "americas"},
    "lan": {"platform": "la1", "regional": "americas"},
    "las": {"platform": "la2", "regional": "americas"},
    "oce": {"platform": "oc1", "regional": "sea"},
    "tr": {"platform": "tr1", "regional": "europe"},
    "ru": {"platform": "ru", "regional": "europe"},
    "jp": {"platform": "jp1", "regional": "asia"},
    "ph": {"platform": "ph2", "regional": "sea"},
    "sg": {"platform": "sg2", "regional": "sea"},
    "th": {"platform": "th2", "regional": "sea"},
    "tw": {"platform": "tw2", "regional": "sea"},
    "vn": {"platform": "vn2", "regional": "sea"},
}

VALID_ROLES = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}
CHECKPOINT_INTERVAL = 500
DATA_DIR = Path("data/solo_queue")


@dataclass
class RateLimiter:
    """Enforce Riot dev-key limits: 20 req/s and 100 req/2min."""

    per_second: int = 20
    per_two_minutes: int = 100
    _second_timestamps: list[float] = field(default_factory=list)
    _window_timestamps: list[float] = field(default_factory=list)

    def wait(self) -> None:
        now = time.monotonic()

        self._second_timestamps = [t for t in self._second_timestamps if now - t < 1.0]
        self._window_timestamps = [t for t in self._window_timestamps if now - t < 120.0]

        sleep_for = 0.0
        if len(self._second_timestamps) >= self.per_second:
            sleep_for = max(sleep_for, 1.0 - (now - self._second_timestamps[0]))
        if len(self._window_timestamps) >= self.per_two_minutes:
            sleep_for = max(sleep_for, 120.0 - (now - self._window_timestamps[0]))

        if sleep_for > 0:
            time.sleep(sleep_for)
            now = time.monotonic()
            self._second_timestamps = [t for t in self._second_timestamps if now - t < 1.0]
            self._window_timestamps = [t for t in self._window_timestamps if now - t < 120.0]

        self._second_timestamps.append(now)
        self._window_timestamps.append(now)


@dataclass
class CollectionState:
    processed_match_ids: set[str] = field(default_factory=set)
    processed_puuids: set[str] = field(default_factory=set)
    stats: dict[tuple[str, str, str], dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"games": 0, "wins": 0}))
    patches_seen: set[str] = field(default_factory=set)
    matches_collected: int = 0
    players_processed: int = 0

    def to_serializable(self) -> dict[str, Any]:
        return {
            "processed_match_ids": sorted(self.processed_match_ids),
            "processed_puuids": sorted(self.processed_puuids),
            "stats": {
                f"{champion}|{role}|{patch}": values
                for (champion, role, patch), values in self.stats.items()
            },
            "patches_seen": sorted(self.patches_seen),
            "matches_collected": self.matches_collected,
            "players_processed": self.players_processed,
        }

    @classmethod
    def from_serializable(cls, data: dict[str, Any]) -> CollectionState:
        state = cls()
        state.processed_match_ids = set(data.get("processed_match_ids", []))
        state.processed_puuids = set(data.get("processed_puuids", []))
        # Compatibilité anciens checkpoints basés sur summonerId
        state.processed_puuids.update(data.get("processed_summoner_ids", []))
        state.patches_seen = set(data.get("patches_seen", []))
        state.matches_collected = data.get("matches_collected", 0)
        state.players_processed = data.get("players_processed", 0)
        for key, values in data.get("stats", {}).items():
            champion, role, patch = key.split("|", 2)
            state.stats[(champion, role, patch)] = values
        return state


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def get_api_key() -> str:
    api_key = os.environ.get("RIOT_API_KEY", "").strip()
    if not api_key:
        logging.error(
            "Variable d'environnement RIOT_API_KEY manquante. "
            "Exemple PowerShell: $env:RIOT_API_KEY = 'RGAPI-...'"
        )
        sys.exit(1)
    return api_key


def parse_patch(game_version: str) -> str:
    parts = game_version.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return game_version


def riot_get(
    url: str,
    api_key: str,
    rate_limiter: RateLimiter,
    params: dict[str, Any] | None = None,
    max_retries: int = 5,
) -> Any:
    headers = {"X-Riot-Token": api_key}

    for attempt in range(max_retries):
        rate_limiter.wait()
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 403:
            logging.error(
                "Erreur 403 Forbidden : clé API invalide ou expirée. "
                "Les clés de développement Riot expirent après 24h — régénérez-en une "
                "sur https://developer.riotgames.com/ et mettez à jour RIOT_API_KEY."
            )
            sys.exit(1)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else min(2 ** attempt, 60)
            logging.warning("Rate limit 429 — attente %.1fs (tentative %d/%d)", wait_seconds, attempt + 1, max_retries)
            time.sleep(wait_seconds)
            continue

        if response.status_code == 404:
            return None

        if response.status_code >= 500:
            wait_seconds = min(2 ** attempt, 30)
            logging.warning("Erreur serveur %d — retry dans %.1fs", response.status_code, wait_seconds)
            time.sleep(wait_seconds)
            continue

        logging.error("Requête échouée (%d): %s", response.status_code, response.text[:300])
        response.raise_for_status()

    raise RuntimeError(f"Échec après {max_retries} tentatives: {url}")


def fetch_league_puuids(platform: str, api_key: str, rate_limiter: RateLimiter) -> list[str]:
    base = f"https://{platform}.api.riotgames.com/lol/league/v4"
    leagues = ["challengerleagues", "grandmasterleagues", "masterleagues"]
    endpoints = [f"{base}/{league}/by-queue/RANKED_SOLO_5x5" for league in leagues]

    puuids: set[str] = set()
    for url, league in zip(endpoints, leagues):
        data = riot_get(url, api_key, rate_limiter)
        entries = data.get("entries", []) if data else []
        for entry in entries:
            puuid = entry.get("puuid")
            if puuid:
                puuids.add(puuid)
        logging.info("Récupéré %d entrées depuis %s (total unique: %d)", len(entries), league, len(puuids))

    return sorted(puuids)


def fetch_puuid_from_summoner_id(
    platform: str, summoner_id: str, api_key: str, rate_limiter: RateLimiter
) -> str | None:
    """Fallback si une entrée league ne contient que summonerId (ancienne API)."""
    url = f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
    data = riot_get(url, api_key, rate_limiter)
    if not data:
        return None
    return data.get("puuid")


def fetch_match_ids(
    regional: str,
    puuid: str,
    api_key: str,
    rate_limiter: RateLimiter,
    count: int = 20,
) -> list[str]:
    url = f"https://{regional}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"queue": 420, "count": count}
    data = riot_get(url, api_key, rate_limiter, params=params)
    return data if isinstance(data, list) else []


def fetch_match_detail(regional: str, match_id: str, api_key: str, rate_limiter: RateLimiter) -> dict[str, Any] | None:
    url = f"https://{regional}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return riot_get(url, api_key, rate_limiter)


def extract_participant_records(match: dict[str, Any]) -> list[dict[str, Any]]:
    info = match.get("info", {})
    patch = parse_patch(info.get("gameVersion", ""))
    records = []

    for participant in info.get("participants", []):
        role = participant.get("teamPosition", "")
        if role not in VALID_ROLES:
            continue
        records.append(
            {
                "champion": participant.get("championName", "Unknown"),
                "role": role,
                "patch": patch,
                "win": bool(participant.get("win", False)),
            }
        )
    return records


def resolve_target_patch(state: CollectionState, patch_arg: str | None) -> str | None:
    if patch_arg:
        return patch_arg
    if not state.patches_seen:
        return None
    return max(state.patches_seen, key=lambda p: tuple(int(x) for x in p.split(".")))


def aggregate_records(
    state: CollectionState,
    records: list[dict[str, Any]],
    target_patch: str | None,
) -> None:
    for record in records:
        state.patches_seen.add(record["patch"])
        if target_patch and record["patch"] != target_patch:
            continue
        key = (record["champion"], record["role"], record["patch"])
        state.stats[key]["games"] += 1
        if record["win"]:
            state.stats[key]["wins"] += 1


def checkpoint_path(region: str) -> Path:
    return DATA_DIR / f"checkpoint_{region}.json"


def save_checkpoint(state: CollectionState, region: str, target_patch: str | None) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "region": region,
        "target_patch": target_patch,
        **state.to_serializable(),
    }
    path = checkpoint_path(region)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp_path.replace(path)
    logging.info("Checkpoint sauvegardé (%d matchs, %d joueurs) -> %s", state.matches_collected, state.players_processed, path)


def load_checkpoint(region: str) -> tuple[CollectionState, str | None] | None:
    path = checkpoint_path(region)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if data.get("region") != region:
        logging.warning("Checkpoint région différente (%s != %s), ignoré", data.get("region"), region)
        return None
    state = CollectionState.from_serializable(data)
    logging.info(
        "Checkpoint chargé: %d matchs, %d joueurs déjà traités",
        state.matches_collected,
        state.players_processed,
    )
    return state, data.get("target_patch")


def build_dataframe(state: CollectionState, target_patch: str | None) -> pd.DataFrame:
    rows = []
    for (champion, role, patch), values in sorted(state.stats.items()):
        if target_patch and patch != target_patch:
            continue
        games = values["games"]
        wins = values["wins"]
        winrate = round(wins / games, 4) if games else 0.0
        rows.append(
            {
                "champion": champion,
                "role": role,
                "patch": patch,
                "games": games,
                "wins": wins,
                "winrate": winrate,
            }
        )
    return pd.DataFrame(rows, columns=["champion", "role", "patch", "games", "wins", "winrate"])


def export_csv(df: pd.DataFrame, region: str, target_patch: str | None) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    patch_label = target_patch or "latest"
    output_path = DATA_DIR / f"soloq_winrates_{region}_{patch_label}.csv"
    df.to_csv(output_path, index=False)
    return output_path


def collect(
    region: str,
    patch: str | None,
    match_count: int,
    resume: bool,
    max_players: int | None = None,
) -> Path:
    if region not in REGION_CONFIG:
        raise ValueError(f"Région inconnue '{region}'. Choix: {', '.join(sorted(REGION_CONFIG))}")

    config = REGION_CONFIG[region]
    platform = config["platform"]
    regional = config["regional"]
    api_key = get_api_key()
    rate_limiter = RateLimiter()

    state = CollectionState()
    target_patch = patch

    if resume:
        loaded = load_checkpoint(region)
        if loaded:
            state, saved_patch = loaded
            if not target_patch and saved_patch:
                target_patch = saved_patch

    start_time = time.monotonic()
    puuids = fetch_league_puuids(platform, api_key, rate_limiter)
    if max_players is not None:
        puuids = puuids[:max_players]
        logging.info("Mode test: limité à %d joueurs", max_players)
    logging.info("Total joueurs Challenger/GM/Master: %d", len(puuids))

    for idx, puuid in enumerate(puuids, start=1):
        if puuid in state.processed_puuids:
            continue

        match_ids = fetch_match_ids(regional, puuid, api_key, rate_limiter, count=match_count)
        new_matches = 0

        for match_id in match_ids:
            if match_id in state.processed_match_ids:
                continue

            match = fetch_match_detail(regional, match_id, api_key, rate_limiter)
            state.processed_match_ids.add(match_id)

            if not match:
                continue

            records = extract_participant_records(match)
            if not records:
                continue

            if target_patch is None:
                for record in records:
                    state.patches_seen.add(record["patch"])
                target_patch = max(state.patches_seen, key=lambda p: tuple(int(x) for x in p.split(".")))
                logging.info("Patch cible auto-détecté: %s", target_patch)

            aggregate_records(state, records, target_patch)
            state.matches_collected += 1
            new_matches += 1

            if state.matches_collected % CHECKPOINT_INTERVAL == 0:
                save_checkpoint(state, region, target_patch)
                elapsed = time.monotonic() - start_time
                logging.info(
                    "Progression: %d/%d joueurs | %d matchs collectés | %.0fs écoulées",
                    state.players_processed,
                    len(puuids),
                    state.matches_collected,
                    elapsed,
                )

        state.processed_puuids.add(puuid)
        state.players_processed += 1

        if idx % 25 == 0 or new_matches > 0:
            elapsed = time.monotonic() - start_time
            logging.info(
                "Joueur %d/%d | +%d matchs | total %d matchs | %.0fs",
                idx,
                len(puuids),
                new_matches,
                state.matches_collected,
                elapsed,
            )

    target_patch = resolve_target_patch(state, target_patch or patch)
    save_checkpoint(state, region, target_patch)

    df = build_dataframe(state, target_patch)
    output_path = export_csv(df, region, target_patch)

    elapsed = time.monotonic() - start_time
    logging.info(
        "Terminé en %.0fs — %d lignes exportées vers %s (patch %s)",
        elapsed,
        len(df),
        output_path,
        target_patch,
    )
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collecte les winrates solo queue par champion/rôle via l'API Riot."
    )
    parser.add_argument(
        "--region",
        default="euw",
        choices=sorted(REGION_CONFIG),
        help="Région de jeu (défaut: euw)",
    )
    parser.add_argument(
        "--patch",
        default=None,
        help='Patch cible, ex: "16.14". Auto-détecté si omis.',
    )
    parser.add_argument(
        "--match-count",
        type=int,
        default=20,
        help="Nombre de matchs récents par joueur (défaut: 20)",
    )
    parser.add_argument(
        "--max-players",
        type=int,
        default=None,
        help="Limite le nombre de joueurs (utile pour tester)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reprendre depuis le dernier checkpoint",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Logs détaillés",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)
    collect(
        region=args.region,
        patch=args.patch,
        match_count=args.match_count,
        resume=args.resume,
        max_players=args.max_players,
    )


if __name__ == "__main__":
    main()
