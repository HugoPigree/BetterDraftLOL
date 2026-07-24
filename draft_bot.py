"""Bot adversaire pour la draft : bans et picks basés sur predict_draft()."""

from __future__ import annotations

from typing import Any, Literal

from suggest_draft import (
    PredictionMode,
    ROLES_ORDER,
    TeamSide,
    build_team_with_meta_fillers,
    champions_playable_on_role,
    get_champion_role_catalog,
    normalize_role,
    slots_to_team,
    soft_assign_roles,
    suggest_ban,
    suggest_bot_pick,
)

ActionType = Literal["ban", "pick"]
BOT_MODE: PredictionMode = "pro"


def _remaining_roles(partial_picks: list[dict[str, str]]) -> list[str]:
    filled = {normalize_role(slot["role"]) for slot in partial_picks if slot.get("role")}
    return [role for role in ROLES_ORDER if role not in filled]


def _used_champions(
    bot_picks: list[dict[str, Any]],
    opponent_picks: list[dict[str, Any]],
) -> set[str]:
    return {
        str(slot.get("champion", "")).strip().casefold()
        for slot in bot_picks + opponent_picks
        if str(slot.get("champion", "")).strip()
    }


def _pad_team_meta(
    partial_picks: list[dict[str, str]],
    catalog: dict[str, list[str]],
    available_champions: list[str],
    reserved: set[str],
    patch: str,
    mode: PredictionMode,
) -> list[dict[str, str]]:
    remaining = _remaining_roles(partial_picks)
    if not remaining:
        team = slots_to_team(partial_picks)
        if len(team) == 5:
            return team
        remaining = ROLES_ORDER.copy()

    padded = build_team_with_meta_fillers(
        partial_picks=partial_picks,
        remaining_roles=remaining,
        catalog=catalog,
        available_champions=available_champions,
        reserved=reserved,
        patch=patch,
        mode=mode,
    )
    if padded is not None:
        return padded

    team = slots_to_team(partial_picks)
    if len(team) == 5:
        return team
    raise ValueError("Impossible de simuler la compo du bot")


def _fallback_ban(
    available_champions: list[str],
    catalog: dict[str, list[str]],
    reserved: set[str],
) -> str:
    for champion in sorted(available_champions, key=str.casefold):
        key = champion.casefold()
        if key in reserved:
            continue
        if catalog.get(champion):
            return champion
    for champion in sorted(available_champions, key=str.casefold):
        if champion.casefold() not in reserved:
            return champion
    raise ValueError("Aucun champion disponible pour le ban du bot")


def _fallback_pick(
    available_champions: list[str],
    remaining_roles: list[str],
    catalog: dict[str, list[str]],
    reserved: set[str],
) -> tuple[str, str]:
    for role in remaining_roles:
        for champion in champions_playable_on_role(available_champions, role, catalog):
            if champion.casefold() not in reserved:
                return champion, role
    raise ValueError("Aucun champion disponible pour le pick du bot")


def choose_bot_ban(
    bot_side: TeamSide,
    bot_picks: list[dict[str, Any]],
    opponent_picks: list[dict[str, Any]],
    patch: str,
    available_champions: list[str],
    mode: PredictionMode = BOT_MODE,
) -> dict[str, Any]:
    """Choisit le ban le plus menaçant pour l'adversaire."""
    catalog = get_champion_role_catalog()
    # Postes inconnus en draft : déduction Meraki pour le scoring uniquement.
    bot_guessed = soft_assign_roles(bot_picks, catalog)
    opponent_guessed = soft_assign_roles(opponent_picks, catalog)
    reserved = _used_champions(bot_picks, opponent_picks)
    pool = [
        champion.strip()
        for champion in available_champions
        if champion.strip() and champion.strip().casefold() not in reserved
    ]
    if not pool:
        raise ValueError("Aucun champion disponible pour le ban du bot")

    bot_team = _pad_team_meta(bot_guessed, catalog, pool, reserved, patch, mode)
    opponent_remaining = _remaining_roles(opponent_guessed) or ROLES_ORDER.copy()

    result = suggest_ban(
        available_champions=pool,
        opponent_partial_picks=opponent_guessed,
        opponent_remaining_roles=opponent_remaining,
        patch=patch,
        team_picks=bot_team,
        team_side=bot_side,
        top_n=1,
        mode=mode,
    )

    suggestions = result.get("suggestions") or []
    if suggestions:
        top = suggestions[0]
        return {
            "action": "ban",
            "champion": top["champion"],
            "role": None,
            "reason": top.get("reason"),
        }

    champion = _fallback_ban(pool, catalog, reserved)
    return {"action": "ban", "champion": champion, "role": None, "reason": None}


def choose_bot_pick(
    bot_side: TeamSide,
    bot_picks: list[dict[str, Any]],
    opponent_picks: list[dict[str, Any]],
    patch: str,
    available_champions: list[str],
    mode: PredictionMode = BOT_MODE,
) -> dict[str, Any]:
    """Choisit un pick cohérent (meta pro + synergie ML + duos mesurés)."""
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

    choice = suggest_bot_pick(
        bot_partial_picks=bot_picks,
        opponent_partial_picks=opponent_picks,
        patch=patch,
        available_champions=pool,
        team_side=bot_side,
        mode=mode,
    )

    champion = choice.get("champion")
    # Le rôle renvoyé n'est qu'une hypothèse de scoring : le client ne doit pas le figer.
    if champion:
        return {
            "action": "pick",
            "champion": champion,
            "role": None,
            "reason": choice.get("reason"),
        }

    fallback_champion, _fallback_role = _fallback_pick(pool, bot_remaining, catalog, reserved)
    return {
        "action": "pick",
        "champion": fallback_champion,
        "role": None,
        "reason": None,
    }


def choose_bot_action(
    action_type: ActionType,
    bot_side: TeamSide,
    bot_picks: list[dict[str, Any]],
    opponent_picks: list[dict[str, Any]],
    patch: str,
    available_champions: list[str],
    mode: PredictionMode = BOT_MODE,
) -> dict[str, Any]:
    """Point d'entrée unique pour le tour du bot."""
    if action_type == "ban":
        return choose_bot_ban(
            bot_side=bot_side,
            bot_picks=bot_picks,
            opponent_picks=opponent_picks,
            patch=patch,
            available_champions=available_champions,
            mode=mode,
        )
    if action_type == "pick":
        return choose_bot_pick(
            bot_side=bot_side,
            bot_picks=bot_picks,
            opponent_picks=opponent_picks,
            patch=patch,
            available_champions=available_champions,
            mode=mode,
        )
    raise ValueError(f"Action invalide: {action_type}")
