"""Bot de draft pour le mode carrière — meta patch + picks préférentiels équipe."""

from __future__ import annotations

import random
from functools import lru_cache
from typing import Any, Literal

from career_meta import ROLES, build_champion_tag_lookup
from suggest_draft import soft_assign_roles, get_champion_role_catalog

ActionType = Literal["ban", "pick"]
TeamSide = Literal["blue", "red"]

COMFORT_SCORE_BONUS = 0.16
SIGNATURE_SCORE_BONUS = 0.34
SPICE_FLOOR = 0.08


@lru_cache(maxsize=1)
def _tag_lookup() -> dict[str, dict[str, list[str]]]:
    return build_champion_tag_lookup()


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


def _vogue_bonus(champion: str, role: str | None, patch: dict[str, Any]) -> float:
    if not role:
        return 0.0
    viable = (patch.get("viable_by_role") or {}).get(role, [])
    if champion not in viable:
        return -0.38
    index = viable.index(champion)
    depth = max(len(viable), 1)
    return 0.14 + (1 - index / depth) * 0.24


def _patch_tag_bonus(champion: str, role: str | None, patch: dict[str, Any]) -> float:
    if not role:
        return 0.0
    tags = _tag_lookup().get(role, {}).get(champion, [])
    shifts = patch.get("tag_shifts") or {}
    return sum(float(shifts.get(tag, 0.0)) for tag in tags) * 0.45


def _identity_tag_bonus(champion: str, role: str | None, identity: dict[str, Any]) -> float:
    if not role:
        return 0.0
    tags = _tag_lookup().get(role, {}).get(champion, [])
    identity_tags = set(identity.get("tags") or [])
    overlap = sum(1 for tag in tags if tag in identity_tags)
    return overlap * 0.07


def _preference_bonus(champion: str, profile: dict[str, Any] | None) -> float:
    if not profile:
        return 0.0
    power = float(profile.get("power", 0.65))
    if champion in (profile.get("signature_picks") or []):
        return SIGNATURE_SCORE_BONUS * power
    if champion in (profile.get("comfort") or []):
        return COMFORT_SCORE_BONUS * power
    return 0.0


def _ban_target_bonus(
    champion: str,
    *,
    patch: dict[str, Any],
    opponent_profiles: list[dict[str, Any]],
) -> float:
    score = 0.0
    for role in ROLES:
        score = max(score, _vogue_bonus(champion, role, patch))
        if score > 0.2:
            break

    for profile in opponent_profiles:
        if champion in (profile.get("signature_picks") or []):
            score += 0.32
        elif champion in (profile.get("comfort") or []):
            score += 0.16
    return score


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
    score = 0.5 + rng.uniform(-0.04, 0.04)

    if action_type == "pick" and role:
        score += _vogue_bonus(champion, role, patch)
        score += _patch_tag_bonus(champion, role, patch)
        score += _identity_tag_bonus(champion, role, identity)
        score += _preference_bonus(champion, profile)

        comfort = (profile.get("comfort") or []) if profile else []
        spice = float(identity.get("spice_chance", 0.1))
        if profile and champion not in comfort and rng.random() < spice:
            score += 0.1
        return score

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
    for (_score, champion), weight in zip(pool, weights, strict=False):
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
    opponent_profiles: list[dict[str, Any]] | None = None,
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
    enemy_profiles = opponent_profiles or []

    if action_type == "pick" and next_role:
        viable = set((patch.get("viable_by_role") or {}).get(next_role, []))
        meta_pool = [champion for champion in pool if champion in viable]
        if meta_pool:
            pool = meta_pool

    scored: list[tuple[float, str]] = []
    for champion in pool:
        if action_type == "ban":
            score = _ban_target_bonus(
                champion,
                patch=patch,
                opponent_profiles=enemy_profiles,
            )
            score += rng.uniform(-0.03, 0.03)
        else:
            score = _score_champion(
                champion=champion,
                role=next_role,
                identity=team_identity,
                patch=patch,
                profile=next_profile,
                action_type=action_type,
                rng=rng,
            )
        scored.append((score, champion))

    top_n = 7 if action_type == "pick" else 6
    chosen = _pick_weighted(scored, rng, top_n=top_n)
    if action_type == "ban":
        return {
            "action": "ban",
            "champion": chosen,
            "role": None,
            "reason": "Ban meta / menace adversaire.",
        }

    return {
        "action": "pick",
        "champion": chosen,
        "role": next_role,
        "reason": f"Pick {team_identity.get('label', 'signature')} — meta + pool équipe.",
    }
