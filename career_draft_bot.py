"""Bot de draft pour le mode carrière — identité équipe + meta fictive."""

from __future__ import annotations

import random
from typing import Any, Literal

from career_meta import ROLES, Role
from suggest_draft import soft_assign_roles, get_champion_role_catalog

ActionType = Literal["ban", "pick"]
TeamSide = Literal["blue", "red"]

COMFORT_PICK_CHANCE = 0.42
SPICE_FLOOR = 0.08


def _used_champions(
    bot_picks: list[dict[str, Any]],
    opponent_picks: list[dict[str, Any]],
) -> set[str]:
    reserved: set[str] = set()
    for slot in bot_picks + opponent_picks:
        champion = str(slot.get("champion", "")).strip()
        if champion:
            reserved.add(champion.casefold())
    return reserved


def _remaining_roles(bot_picks: list[dict[str, Any]]) -> list[str]:
    catalog = get_champion_role_catalog()
    guessed = soft_assign_roles(bot_picks, catalog)
    filled = {slot.get("role") for slot in guessed if slot.get("role")}
    return [role for role in ROLES if role not in filled]


def _profile_for_role(
    profiles: list[dict[str, Any]],
    role: str,
) -> dict[str, Any] | None:
    for profile in profiles:
        if profile.get("role") == role:
            return profile
    return None


def _score_champion(
    *,
    champion: str,
    role: str | None,
    identity: dict[str, Any],
    patch: dict[str, Any],
    profile: dict[str, Any] | None,
    action_type: ActionType,
    rng: random.Random,
) -> float:
    shifts = patch.get("tag_shifts") or {}
    identity_tags = set(identity.get("tags") or [])
    score = 0.55 + rng.uniform(-0.05, 0.05)

    pool_data_tags: list[str] = []
    if role:
        viable = (patch.get("viable_by_role") or {}).get(role, [])
        if champion not in viable:
            score -= 0.35

    if profile and champion in (profile.get("comfort") or []):
        score += 0.28 * float(profile.get("power", 0.65))

    if action_type == "ban":
        if profile and champion in (profile.get("comfort") or []):
            score += 0.22
        return score

    spice = float(identity.get("spice_chance", 0.1))
    if profile and champion not in (profile.get("comfort") or []) and rng.random() < spice:
        score += 0.12

    return score


def _pick_weighted(
    scored: list[tuple[float, str]],
    rng: random.Random,
    *,
    top_n: int = 5,
) -> str:
    if not scored:
        raise ValueError("Aucun candidat pour le bot carrière")
    pool = sorted(scored, key=lambda item: (-item[0], item[1]))[:top_n]
    weights = [max(0.05, score) for score, _ in pool]
    total = sum(weights)
    roll = rng.random() * total
    cursor = 0.0
    for (score, champion), weight in zip(pool, weights, strict=False):
        cursor += weight
        if roll <= cursor:
            return champion
    return pool[-1][1]


def choose_career_bot_action(
    *,
    action_type: ActionType,
    bot_side: TeamSide,
    bot_picks: list[dict[str, Any]],
    opponent_picks: list[dict[str, Any]],
    available_champions: list[str],
    team_identity: dict[str, Any],
    team_profiles: list[dict[str, Any]],
    patch: dict[str, Any],
    seed: int | None = None,
) -> dict[str, Any]:
    del bot_side
    rng = random.Random(seed)
    reserved = _used_champions(bot_picks, opponent_picks)
    pool = [champion for champion in available_champions if champion.casefold() not in reserved]
    if not pool:
        raise ValueError("Aucun champion disponible pour le bot carrière")

    remaining_roles = _remaining_roles(bot_picks)
    next_role = remaining_roles[0] if remaining_roles else None
    next_profile = _profile_for_role(team_profiles, next_role) if next_role else None

    if action_type == "pick" and next_profile and rng.random() < COMFORT_PICK_CHANCE:
        for comfort in next_profile.get("comfort") or []:
            if comfort in pool:
                return {
                    "action": "pick",
                    "champion": comfort,
                    "role": next_role,
                    "reason": f"Comfort pick {next_profile.get('player', 'joueur')}.",
                }

    if action_type == "pick" and next_role:
        viable = set((patch.get("viable_by_role") or {}).get(next_role, []))
        pool = [champion for champion in pool if not viable or champion in viable] or pool

    scored: list[tuple[float, str]] = []
    for champion in pool:
        score = _score_champion(
            champion=champion,
            role=next_role if action_type == "pick" else None,
            identity=team_identity,
            patch=patch,
            profile=next_profile if action_type == "pick" else None,
            action_type=action_type,
            rng=rng,
        )
        if action_type == "ban":
            for profile in team_profiles:
                if champion in (profile.get("comfort") or []):
                    score += 0.15
        scored.append((score, champion))

    chosen = _pick_weighted(scored, rng)
    if action_type == "ban":
        return {
            "action": "ban",
            "champion": chosen,
            "role": None,
            "reason": "Ban orienté identité équipe.",
        }

    return {
        "action": "pick",
        "champion": chosen,
        "role": next_role,
        "reason": f"Pick {team_identity.get('label', 'signature')}.",
    }
