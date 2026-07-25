"""Bot de draft calé sur les signatures d'une équipe pro."""

from __future__ import annotations

import random
from typing import Any, Literal

from draft_bot import (
    _fallback_ban,
    _fallback_pick,
    _remaining_roles,
    _used_champions,
    choose_bot_action,
)
from player_signatures import (
    SIGNATURE_PICK_RATE_THRESHOLD,
    build_signature_lookup,
    get_player_signatures,
)
from suggest_draft import (
    PredictionMode,
    TeamSide,
    get_champion_role_catalog,
    soft_assign_roles,
)

ActionType = Literal["ban", "pick"]
SIGNATURE_PICK_CHANCE = 0.38


def warmup_worlds_draft_bot() -> None:
    """Pré-charge les caches lourds avant la première draft Worlds."""
    build_signature_lookup()
    get_champion_role_catalog()


def _next_role_player(
    bot_picks: list[dict[str, Any]],
    team_roster: dict[str, str],
) -> tuple[str | None, str | None]:
    catalog = get_champion_role_catalog()
    guessed = soft_assign_roles(bot_picks, catalog)
    remaining = _remaining_roles(guessed)
    if not remaining:
        return None, None
    role = remaining[0]
    player = team_roster.get(role)
    return role, player


def _maybe_signature_pick(
    *,
    role: str,
    player: str,
    available_champions: list[str],
    reserved: set[str],
    rng: random.Random,
) -> dict[str, Any] | None:
    signatures = get_player_signatures(player, role, top_n=6)
    for signature in signatures:
        if signature.pick_rate < SIGNATURE_PICK_RATE_THRESHOLD:
            continue
        champion = signature.champion
        if champion.casefold() in reserved:
            continue
        if champion not in available_champions:
            continue
        if rng.random() > SIGNATURE_PICK_CHANCE:
            continue
        return {
            "action": "pick",
            "champion": champion,
            "role": None,
            "reason": (
                f"Signature pick de {player} "
                f"({signature.pick_rate * 100:.0f}% de pool, {signature.games} games pro)"
            ),
        }
    return None


def _fast_bot_ban(
    bot_picks: list[dict[str, Any]],
    opponent_picks: list[dict[str, Any]],
    available_champions: list[str],
) -> dict[str, Any]:
    catalog = get_champion_role_catalog()
    reserved = _used_champions(bot_picks, opponent_picks)
    pool = [
        champion.strip()
        for champion in available_champions
        if champion.strip() and champion.strip().casefold() not in reserved
    ]
    if not pool:
        raise ValueError("Aucun champion disponible pour le ban du bot")
    champion = _fallback_ban(pool, catalog, reserved)
    return {"action": "ban", "champion": champion, "role": None, "reason": "Ban meta rapide"}


def _fast_bot_pick(
    bot_picks: list[dict[str, Any]],
    opponent_picks: list[dict[str, Any]],
    available_champions: list[str],
) -> dict[str, Any]:
    catalog = get_champion_role_catalog()
    reserved = _used_champions(bot_picks, opponent_picks)
    pool = [
        champion.strip()
        for champion in available_champions
        if champion.strip() and champion.strip().casefold() not in reserved
    ]
    if not pool:
        raise ValueError("Aucun champion disponible pour le pick du bot")
    bot_guessed = soft_assign_roles(bot_picks, catalog)
    bot_remaining = _remaining_roles(bot_guessed)
    if not bot_remaining:
        raise ValueError("La compo du bot est déjà complète")
    champion, _role = _fallback_pick(pool, bot_remaining, catalog, reserved)
    return {"action": "pick", "champion": champion, "role": None, "reason": "Pick meta rapide"}


def choose_team_bot_action(
    action_type: ActionType,
    bot_side: TeamSide,
    bot_picks: list[dict[str, Any]],
    opponent_picks: list[dict[str, Any]],
    patch: str,
    available_champions: list[str],
    team_roster: dict[str, str],
    mode: PredictionMode = "pro",
    *,
    seed: int | None = None,
    fast: bool = True,
) -> dict[str, Any]:
    """Draft bot Worlds : signatures + fallback rapide (sans ML lourde)."""
    if action_type == "pick" and team_roster:
        rng = random.Random(seed)
        reserved = {
            str(slot.get("champion", "")).strip().casefold()
            for slot in bot_picks + opponent_picks
            if str(slot.get("champion", "")).strip()
        }
        pool = [
            champion.strip()
            for champion in available_champions
            if champion.strip() and champion.strip().casefold() not in reserved
        ]
        role, player = _next_role_player(bot_picks, team_roster)
        if role and player and pool:
            signature_move = _maybe_signature_pick(
                role=role,
                player=player,
                available_champions=pool,
                reserved=reserved,
                rng=rng,
            )
            if signature_move:
                return signature_move

    if fast:
        if action_type == "ban":
            return _fast_bot_ban(bot_picks, opponent_picks, available_champions)
        if action_type == "pick":
            return _fast_bot_pick(bot_picks, opponent_picks, available_champions)

    return choose_bot_action(
        action_type=action_type,
        bot_side=bot_side,
        bot_picks=bot_picks,
        opponent_picks=opponent_picks,
        patch=patch,
        available_champions=available_champions,
        mode=mode,
    )
