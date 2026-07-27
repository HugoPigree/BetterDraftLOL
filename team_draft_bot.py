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
from predict_draft import get_meraki_context
from pro_force import is_pro_viable_on_role
from suggest_draft import (
    PredictionMode,
    TeamSide,
    get_champion_role_catalog,
    is_champion_in_meta_pool_for_role,
    soft_assign_roles,
)

ActionType = Literal["ban", "pick"]
SIGNATURE_PICK_CHANCE = 0.38


def warmup_worlds_draft_bot() -> None:
    """Pré-charge les caches lourds avant la première draft Worlds."""
    from player_signatures import warmup_signature_lookup

    warmup_signature_lookup()
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
    patch: str,
    catalog: dict[str, list[str]],
    rng: random.Random,
) -> dict[str, Any] | None:
    """Signature pick optionnelle — uniquement si le champion est dans le pool meta pro."""
    signatures = get_player_signatures(player, role, top_n=6)
    signature_pool = [item for item in signatures if item.pick_rate >= SIGNATURE_PICK_RATE_THRESHOLD]
    rng.shuffle(signature_pool)
    signature_chance = 0.22 + rng.random() * 0.24
    for signature in signature_pool:
        champion = signature.champion
        if champion.casefold() in reserved:
            continue
        if champion not in available_champions:
            continue
        if not is_champion_in_meta_pool_for_role(champion, role, catalog, patch):
            continue
        champion_features, _, lookup_by_norm = get_meraki_context()
        if not is_pro_viable_on_role(champion, role, champion_features, lookup_by_norm):
            continue
        if rng.random() > signature_chance:
            continue
        return {
            "action": "pick",
            "champion": champion,
            "role": role,
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
    """Draft bot Worlds — même pipeline ML que Draft vs Bot (suggest_bot_pick / suggest_ban).

    ``fast=True`` (défaut prod) n'active plus de chemin alphabétique : il garde le flag
    pour compatibilité API. Seule exception : signature pick joueur (~38%) si le champion
    est dans le pool meta pro filtré (>= MIN_GAMES_EXCLUSION).
    """
    del fast  # conservé pour compat API ; le pipeline ML complet est toujours utilisé

    bot_rng_seed = seed
    if bot_rng_seed is None:
        bot_rng_seed = hash(
            (
                action_type,
                bot_side,
                patch.strip(),
                tuple(sorted(available_champions)),
                tuple(str(slot.get("champion", "")) for slot in bot_picks + opponent_picks),
            )
        ) & 0x7FFFFFFF

    if action_type == "pick" and team_roster:
        rng = random.Random(bot_rng_seed)
        catalog = get_champion_role_catalog()
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
                patch=patch.strip(),
                catalog=catalog,
                rng=rng,
            )
            if signature_move:
                return signature_move

    return choose_bot_action(
        action_type=action_type,
        bot_side=bot_side,
        bot_picks=bot_picks,
        opponent_picks=opponent_picks,
        patch=patch,
        available_champions=available_champions,
        mode=mode,
        seed=bot_rng_seed,
    )
