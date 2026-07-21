#!/usr/bin/env python3
"""Statistiques descriptives Oracle's Elixir par champion/rôle — TEXTE UNIQUEMENT.

NE JAMAIS utiliser ces métriques (golddiffat15, dpm, csdiffat15, etc.) comme entrées
du modèle prédictif : ce sont des stats mesurées PENDANT la game (fuite de données).

Modules autorisés à importer ce fichier :
  - suggest_draft (justifications pick/ban)
  - api (enrichissement descriptif post-prédiction, sans toucher aux scores)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from build_duo_dataset import load_player_rows
from pro_force import DEFAULT_ORACLE_CSV, ORACLE_POSITION_TO_ROLE

logger = logging.getLogger(__name__)

MIN_GAMES_DESCRIPTIVE = 10
DESCRIPTIVE_DISCLAIMER = "(statistique historique moyenne)"

# Garde-fou : seuls ces modules peuvent appeler les helpers de texte.
ALLOWED_DESCRIPTIVE_CALLERS = frozenset(
    {
        "suggest_draft",
        "api_descriptive_enrichment",
        "champion_profile_stats",
    }
)

_profile_stats_lookup: dict[tuple[str, str], ChampionProfileStats] | None = None
_profile_oracle_path: Path | None = None

DescriptiveContext = Literal["counter", "synergy", "neutral", "threat"]


@dataclass(frozen=True)
class ChampionProfileStats:
    champion: str
    role: str
    games: int
    golddiffat15: float | None
    dpm: float | None
    csdiffat15: float | None


def assert_descriptive_use_only(caller: str) -> None:
    """Vérifie que les stats descriptives ne sont pas utilisées dans un score."""
    if caller not in ALLOWED_DESCRIPTIVE_CALLERS:
        raise RuntimeError(
            "champion_profile_stats ne doit servir qu'à enrichir du texte explicatif, "
            f"pas au calcul de score (appelant interdit: {caller!r})."
        )


def _normalize_role(role: str) -> str:
    role_upper = role.strip().upper()
    return {"SUPPORT": "UTILITY"}.get(role_upper, role_upper)


def compute_champion_profile_stats(
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
    min_games: int = MIN_GAMES_DESCRIPTIVE,
) -> dict[tuple[str, str], ChampionProfileStats]:
    """Calcule les moyennes golddiffat15, dpm et csdiffat15 par champion/rôle."""
    if not oracle_csv.exists():
        logger.warning("Oracle CSV introuvable pour stats descriptives: %s", oracle_csv)
        return {}

    players = load_player_rows(oracle_csv)
    if players.empty:
        return {}

    stat_columns = ["golddiffat15", "dpm", "csdiffat15"]
    for column in stat_columns:
        if column not in players.columns:
            logger.warning("Colonne Oracle absente pour stats descriptives: %s", column)
            return {}

    frame = players.copy()
    frame["role"] = frame["position"].map(ORACLE_POSITION_TO_ROLE)
    frame = frame.dropna(subset=["role", "champion"])
    frame["champion"] = frame["champion"].astype(str).str.strip()
    for column in stat_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    grouped = (
        frame.groupby(["champion", "role"], as_index=False)
        .agg(
            games=("champion", "count"),
            golddiffat15=("golddiffat15", "mean"),
            dpm=("dpm", "mean"),
            csdiffat15=("csdiffat15", "mean"),
        )
    )
    grouped = grouped[grouped["games"] >= min_games]

    lookup: dict[tuple[str, str], ChampionProfileStats] = {}
    for _, row in grouped.iterrows():
        key = (str(row["champion"]), str(row["role"]))
        lookup[key] = ChampionProfileStats(
            champion=key[0],
            role=key[1],
            games=int(row["games"]),
            golddiffat15=_maybe_float(row["golddiffat15"]),
            dpm=_maybe_float(row["dpm"]),
            csdiffat15=_maybe_float(row["csdiffat15"]),
        )

    logger.info("Stats descriptives chargées: %d paires champion/rôle", len(lookup))
    return lookup


def _maybe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def get_champion_profile_stats_lookup(
    oracle_csv: Path = DEFAULT_ORACLE_CSV,
) -> dict[tuple[str, str], ChampionProfileStats]:
    global _profile_stats_lookup, _profile_oracle_path
    if _profile_stats_lookup is None or _profile_oracle_path != oracle_csv:
        _profile_stats_lookup = compute_champion_profile_stats(oracle_csv)
        _profile_oracle_path = oracle_csv
    return _profile_stats_lookup


def reset_champion_profile_stats_state() -> None:
    global _profile_stats_lookup, _profile_oracle_path
    _profile_stats_lookup = None
    _profile_oracle_path = None


def lookup_champion_profile_stats(
    champion: str,
    role: str,
    lookup: dict[tuple[str, str], ChampionProfileStats] | None = None,
) -> ChampionProfileStats | None:
    role_norm = _normalize_role(role)
    champion_clean = champion.strip()
    table = lookup if lookup is not None else get_champion_profile_stats_lookup()

    direct = table.get((champion_clean, role_norm))
    if direct is not None:
        return direct

    folded = champion_clean.casefold()
    for (name, slot_role), stats in table.items():
        if slot_role == role_norm and name.casefold() == folded:
            return stats
    return None


def _format_signed_int(value: float) -> str:
    rounded = int(round(value))
    if rounded > 0:
        return f"+{rounded}"
    return str(rounded)


def _format_signed_cs(value: float) -> str:
    rounded = int(round(value))
    if rounded > 0:
        return f"+{rounded}"
    return str(rounded)


def _primary_lane_descriptor(
    stats: ChampionProfileStats,
    role_fr: str,
) -> str | None:
    if stats.golddiffat15 is not None and abs(stats.golddiffat15) >= 50:
        if stats.golddiffat15 >= 0:
            return (
                f"un avantage moyen de {_format_signed_int(stats.golddiffat15)} gold "
                f"à 15 minutes en {role_fr}"
            )
        return (
            f"un retard moyen de {_format_signed_int(stats.golddiffat15)} gold "
            f"à 15 minutes en {role_fr}"
        )

    if stats.csdiffat15 is not None and abs(stats.csdiffat15) >= 3:
        if stats.csdiffat15 >= 0:
            return (
                f"un avantage moyen de {_format_signed_cs(stats.csdiffat15)} CS "
                f"à 15 minutes en {role_fr}"
            )
        return (
            f"un déficit moyen de {_format_signed_cs(stats.csdiffat15)} CS "
            f"à 15 minutes en {role_fr}"
        )

    if stats.dpm is not None:
        return f"une moyenne de {stats.dpm:.0f} DPM en {role_fr}"

    return None


def format_descriptive_stats_clause(
    champion: str,
    role: str,
    *,
    caller: str,
    role_fr: str | None = None,
    context: DescriptiveContext = "neutral",
) -> str | None:
    """Phrase descriptive à ajouter aux justifications (jamais au score)."""
    assert_descriptive_use_only(caller)

    stats = lookup_champion_profile_stats(champion, role)
    if stats is None:
        return None

    role_label = role_fr or role.lower()
    descriptor = _primary_lane_descriptor(stats, role_label)
    if descriptor is None:
        return None

    suffix = ""
    if context == "counter":
        suffix = ", cohérent avec son profil de counter favorable ici"
    elif context == "threat":
        suffix = ", signal d'une lane adverse historiquement dominante"
    elif context == "synergy":
        suffix = ", profil de jeu pro typique pour ce rôle"

    return (
        f"{stats.champion} affiche historiquement {descriptor}{suffix}. "
        f"{DESCRIPTIVE_DISCLAIMER}"
    )


def build_team_synergy_explanation(
    insight: dict[str, Any],
    *,
    caller: str,
) -> str:
    """Construit le texte de synthèse synergie avec contexte descriptif."""
    assert_descriptive_use_only(caller)

    top = insight["top_contributor"]
    least = insight["least_contributor"]
    top_pts = float(top["marginal_points"])
    least_pts = float(least["marginal_points"])

    parts = [
        f"{top['champion']} contribue le plus à la synergie de cette équipe "
        f"({top_pts:+.1f} pt)"
    ]

    if least["champion"] != top["champion"]:
        if least_pts < 0:
            parts.append(
                f"{least['champion']} affaiblit la synergie globale ({least_pts:+.1f} pt)"
            )
        else:
            least_suffix = ", voire négatif" if least_pts <= 0.05 else ""
            parts.append(
                f"{least['champion']} contribue le moins "
                f"({least_pts:+.1f} pt{least_suffix})"
            )

    base = ", ".join(parts) + "."

    top_stats = format_descriptive_stats_clause(
        top["champion"],
        top["role"],
        caller=caller,
        context="synergy",
    )
    if top_stats:
        return f"{base} {top_stats}"
    return base


def enrich_predict_response_descriptions(result: dict[str, Any]) -> dict[str, Any]:
    """Ajoute des textes descriptifs à la réponse /predict sans modifier les scores."""
    assert_descriptive_use_only("api_descriptive_enrichment")

    enriched = dict(result)
    for side in ("blue", "red"):
        team = dict(enriched[side])
        insight = dict(team["synergy_insight"])
        insight["explanation"] = build_team_synergy_explanation(
            insight,
            caller="api_descriptive_enrichment",
        )
        team["synergy_insight"] = insight
        enriched[side] = team
    return enriched
