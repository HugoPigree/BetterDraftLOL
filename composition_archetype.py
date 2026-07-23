"""Heuristiques de cohérence d'archétype de composition (Meraki attributeRatings + roles)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from build_training_dataset import (
    ATTRIBUTE_COLUMNS,
    DEFAULT_MERAKI_CACHE,
    MERAKI_URL,
    load_meraki_champions,
    normalize_name,
    resolve_champion_name,
)
from predict_draft import get_meraki_context

logger = logging.getLogger(__name__)

ENGAGE_ROLE_WEIGHTS: dict[str, float] = {
    "VANGUARD": 1.0,
    "CATCHER": 0.9,
    "DIVER": 0.7,
}
PEEL_ROLE_WEIGHTS: dict[str, float] = {
    "ENCHANTER": 1.0,
    "WARDEN": 0.9,
}
SCALING_CARRY_ROLES = frozenset({"MARKSMAN", "MAGE", "ARTILLERY", "BURST", "SPECIALIST"})
PHYSICAL_ADAPTIVE = frozenset({"PHYSICAL_DAMAGE"})
MAGIC_ADAPTIVE = frozenset({"MAGIC_DAMAGE"})

# Pénalités / bonus internes (score_archetype_coherence renvoie 0..1 avant pondération bot).
PENALTY_EARLY_WITHOUT_PLAN = 0.40
PENALTY_FRAGILE_CARRY_IN_DIVE = 0.50
PENALTY_MONO_DAMAGE = 0.30
BONUS_FILLS_PEEL_GAP = 0.18
BONUS_BALANCES_DAMAGE = 0.14

NEUTRAL_RATING = 1.5


@lru_cache(maxsize=1)
def _adaptive_type_lookup() -> dict[str, str | None]:
    champions = load_meraki_champions(MERAKI_URL, DEFAULT_MERAKI_CACHE)
    lookup: dict[str, str | None] = {}
    for key, payload in champions.items():
        adaptive = payload.get("adaptiveType")
        lookup[key] = str(adaptive) if adaptive else None
        display = payload.get("name", key)
        lookup[normalize_name(display)] = lookup[key]
    return lookup


def _resolve_team_champions(team_champions: list[str]) -> list[str]:
    champion_features, _, lookup_by_norm = get_meraki_context()
    resolved: list[str] = []
    for name in team_champions:
        key = resolve_champion_name(name.strip(), champion_features, lookup_by_norm)
        if key is None:
            logger.debug("Champion Meraki introuvable pour archétype: %s", name)
            continue
        resolved.append(key)
    return resolved


def _ratings_for(key: str) -> dict[str, float]:
    champion_features, _, _ = get_meraki_context()
    payload = champion_features.get(key, {})
    raw = payload.get("attributeRatings") or {}
    return {
        attr: float(raw.get(attr) if raw.get(attr) is not None else NEUTRAL_RATING)
        for attr in ATTRIBUTE_COLUMNS
    }


def _roles_for(key: str) -> list[str]:
    champion_features, _, _ = get_meraki_context()
    return list(champion_features.get(key, {}).get("roles") or [])


def _adaptive_for(key: str) -> str | None:
    lookup = _adaptive_type_lookup()
    if key in lookup:
        return lookup[key]
    return lookup.get(normalize_name(key))


def _champion_profile(key: str) -> dict[str, Any]:
    return {
        "key": key,
        "ratings": _ratings_for(key),
        "roles": _roles_for(key),
        "adaptive_type": _adaptive_for(key),
        "power_curve": _champion_power_curve(_ratings_for(key)),
    }


def _champion_power_curve(ratings: dict[str, float]) -> float:
    """Score par champion entre -1 (early) et +1 (late)."""
    early = (ratings["damage"] + ratings["mobility"]) / 2.0
    late = (ratings["toughness"] + ratings["utility"]) / 2.0
    total = early + late
    if total <= 0:
        return 0.0
    return max(-1.0, min(1.0, (late - early) / total))


def _role_weight_sum(roles: list[str], weights: dict[str, float]) -> float:
    return sum(weights.get(role, 0.0) for role in roles)


def _mean_utility(profiles: list[dict[str, Any]]) -> float:
    if not profiles:
        return NEUTRAL_RATING
    return sum(profile["ratings"]["utility"] for profile in profiles) / len(profiles)


def _damage_type_counts(profiles: list[dict[str, Any]]) -> tuple[int, int, int]:
    physical = magic = other = 0
    for profile in profiles:
        adaptive = profile.get("adaptive_type")
        if adaptive in PHYSICAL_ADAPTIVE:
            physical += 1
        elif adaptive in MAGIC_ADAPTIVE:
            magic += 1
        elif adaptive:
            other += 1
    return physical, magic, other


def compute_composition_archetype(team_champions: list[str]) -> dict[str, Any]:
    """Évalue le profil d'archétype d'une équipe (Meraki attributeRatings + roles)."""
    keys = _resolve_team_champions(team_champions)
    if not keys:
        return {
            "power_curve": 0.0,
            "engage_score": 0.0,
            "peel_score": 0.0,
            "damage_profile": {
                "physical_count": 0,
                "magic_count": 0,
                "magic_ratio": 0.5,
                "damage_balance": 1.0,
            },
            "team_size": 0,
        }

    profiles = [_champion_profile(key) for key in keys]
    team_size = len(profiles)

    power_curve = sum(profile["power_curve"] for profile in profiles) / team_size

    engage_raw = sum(
        _role_weight_sum(profile["roles"], ENGAGE_ROLE_WEIGHTS) for profile in profiles
    )
    max_engage = team_size * max(ENGAGE_ROLE_WEIGHTS.values())
    engage_score = engage_raw / max_engage if max_engage else 0.0

    peel_role_raw = sum(
        _role_weight_sum(profile["roles"], PEEL_ROLE_WEIGHTS) for profile in profiles
    )
    utility_bonus = max(0.0, (_mean_utility(profiles) - 1.5) / 1.5) * 0.35
    max_peel = team_size * (max(PEEL_ROLE_WEIGHTS.values()) + 0.35)
    peel_score = min(1.0, (peel_role_raw + utility_bonus * team_size) / max_peel)

    physical, magic, other = _damage_type_counts(profiles)
    typed = physical + magic
    if typed == 0:
        magic_ratio = 0.5
        damage_balance = 1.0
    else:
        magic_ratio = magic / typed
        damage_balance = 1.0 - abs(magic_ratio - 0.5) * 2.0

    return {
        "power_curve": round(power_curve, 4),
        "engage_score": round(engage_score, 4),
        "peel_score": round(peel_score, 4),
        "damage_profile": {
            "physical_count": physical,
            "magic_count": magic,
            "other_count": other,
            "magic_ratio": round(magic_ratio, 4),
            "damage_balance": round(damage_balance, 4),
        },
        "team_size": team_size,
    }


def _is_fragile_scaling_carry(profile: dict[str, Any]) -> bool:
    ratings = profile["ratings"]
    roles = profile["roles"]
    if not any(role in SCALING_CARRY_ROLES for role in roles):
        return False
    fragile = ratings["mobility"] <= 1.5 and ratings["toughness"] <= 1.5
    high_damage = ratings["damage"] >= 2.5
    low_utility = ratings["utility"] <= 1.5
    return fragile and high_damage and low_utility


def _candidate_adds_peel(profile: dict[str, Any]) -> bool:
    peel_roles = _role_weight_sum(profile["roles"], PEEL_ROLE_WEIGHTS)
    return peel_roles >= 0.9 or profile["ratings"]["utility"] >= 2.5


def _team_has_scaling_anchor(profiles: list[dict[str, Any]]) -> bool:
    return any(profile["power_curve"] > 0.05 for profile in profiles) or any(
        _is_fragile_scaling_carry(profile) for profile in profiles
    )


def _team_early_aggressive(profiles: list[dict[str, Any]]) -> bool:
    if not profiles:
        return False
    avg_curve = sum(profile["power_curve"] for profile in profiles) / len(profiles)
    engage = sum(
        _role_weight_sum(profile["roles"], ENGAGE_ROLE_WEIGHTS) for profile in profiles
    ) / len(profiles)
    return avg_curve < -0.10 and engage >= 0.45


def _mono_damage_risk(archetype: dict[str, Any]) -> bool:
    balance = float(archetype["damage_profile"]["damage_balance"])
    typed = (
        archetype["damage_profile"]["physical_count"]
        + archetype["damage_profile"]["magic_count"]
    )
    return typed >= 3 and balance < 0.45


def _candidate_balances_damage(
    candidate: dict[str, Any],
    so_far_profiles: list[dict[str, Any]],
) -> bool:
    combined = so_far_profiles + [candidate]
    before = compute_composition_archetype([p["key"] for p in so_far_profiles])
    after = compute_composition_archetype([p["key"] for p in combined])
    return after["damage_profile"]["damage_balance"] > before["damage_profile"]["damage_balance"] + 0.08


def score_archetype_coherence(team_champions_so_far: list[str], candidate: str) -> float:
    """Simule l'ajout du candidat et retourne un score de cohérence entre 0 et 1."""
    so_far_keys = _resolve_team_champions(team_champions_so_far)
    candidate_key = _resolve_team_champions([candidate])
    if not candidate_key:
        return 0.5
    candidate_key = candidate_key[0]

    team_keys = so_far_keys + [candidate_key]
    team_archetype = compute_composition_archetype(team_keys)
    so_far_archetype = compute_composition_archetype(so_far_keys) if so_far_keys else None

    so_far_profiles = [_champion_profile(key) for key in so_far_keys]
    candidate_profile = _champion_profile(candidate_key)

    score = 1.0

    # (a) Comp early sans plan scaling/peel
    if team_archetype["team_size"] >= 4:
        early_heavy = team_archetype["power_curve"] < -0.12
        low_peel = team_archetype["peel_score"] < 0.22
        no_scaling_plan = not _team_has_scaling_anchor(
            [_champion_profile(key) for key in team_keys]
        )
        if early_heavy and low_peel and no_scaling_plan:
            score -= PENALTY_EARLY_WITHOUT_PLAN

    # (b) Carry fragile dans une comp deja early-aggressive sans peel
    if len(so_far_keys) >= 4 and _is_fragile_scaling_carry(candidate_profile):
        if so_far_archetype and _team_early_aggressive(so_far_profiles):
            if so_far_archetype["peel_score"] < 0.28 and not _candidate_adds_peel(
                candidate_profile
            ):
                score -= PENALTY_FRAGILE_CARRY_IN_DIVE

    # (c) Mono-damage
    if _mono_damage_risk(team_archetype):
        balance = float(team_archetype["damage_profile"]["damage_balance"])
        severity = (0.45 - balance) / 0.45
        score -= PENALTY_MONO_DAMAGE * max(0.0, min(1.0, severity))

    # Bonus : comble un manque de peel
    if so_far_archetype and so_far_archetype["peel_score"] < 0.22:
        if _candidate_adds_peel(candidate_profile):
            score += BONUS_FILLS_PEEL_GAP

    # Bonus : equilibre AD/AP
    if so_far_archetype and _mono_damage_risk(so_far_archetype):
        if _candidate_balances_damage(candidate_profile, so_far_profiles):
            score += BONUS_BALANCES_DAMAGE

    return round(max(0.0, min(1.0, score)), 4)
