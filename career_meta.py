"""Meta fictive du mode carrière LEC — patches, identités équipe, profils joueurs."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Literal

Role = Literal["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
ROLES: tuple[Role, ...] = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")

DEFAULT_POOL_JSON = Path("data/career_champion_pool.json")
PATCH_ROTATION_WEEKS = 2

_PATCH_SHIFT_TEMPLATES: list[list[tuple[str, float]]] = [
    [("engage", 0.12), ("scaling", -0.08), ("roam", 0.06)],
    [("poke", 0.1), ("early", -0.06), ("disengage", 0.05)],
    [("scaling", 0.11), ("burst", -0.07), ("frontline", 0.05)],
    [("skirmish", 0.09), ("split", 0.06), ("teamfight", -0.05)],
    [("early", 0.1), ("sustain", -0.05), ("pick", 0.07)],
]

_PATCH_NOTES_LINES: dict[str, str] = {
    "engage": "Les comps engage gagnent en fiabilité en mid game.",
    "disengage": "Disengage et peel plus valorisés en teamfight.",
    "poke": "Les lanes poke contrôlent mieux les objectifs.",
    "scaling": "Les comps scaling ont plus de marge late.",
    "early": "Le tempo early est puni si mal exécuté.",
    "skirmish": "Skirmish 3v3 autour des crabs plus décisif.",
    "split": "Split push et side pressure reviennent en force.",
    "frontline": "Frontline premium en draft.",
    "roam": "Roams mid/jungle plus récompensés.",
    "peel": "Protect carry devient plus viable.",
    "burst": "Burst picks plus menaçants en side.",
    "sustain": "Sustain et long fights favorisées.",
    "pick": "Vision et picks isolés plus rentables.",
    "teamfight": "5v5 structurés légèrement buffés.",
}


def _load_pool_data(json_path: Path = DEFAULT_POOL_JSON) -> dict[str, Any]:
    if not json_path.exists():
        raise FileNotFoundError(f"Pool carrière introuvable: {json_path}")
    return json.loads(json_path.read_text(encoding="utf-8"))


def _normalize_tag(tag: str) -> str:
    if tag in {"pick", "protect", "safe", "utility", "dps", "mobility", "reset", "push", "siege"}:
        return tag if tag in _PATCH_NOTES_LINES else "skirmish"
    return tag


def _champions_by_role(pool_data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_role: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    champions = pool_data.get("champions") or {}
    for name, payload in champions.items():
        roles = payload.get("roles") or []
        tags = [_normalize_tag(tag) for tag in (payload.get("tags") or [])]
        for role in roles:
            mapped = "UTILITY" if role == "SUPPORT" else role
            if mapped not in by_role:
                continue
            by_role[mapped].append({"name": name, "tags": tags})
    return by_role


def _seed_int(seed: int | str | None) -> int:
    if seed is None:
        return 0
    if isinstance(seed, int):
        return seed & 0x7FFFFFFF
    value = 0
    for char in str(seed):
        value = (value * 31 + ord(char)) & 0x7FFFFFFF
    return value


def patch_index_for_week(week: int) -> int:
    return max(0, (max(1, week) - 1) // PATCH_ROTATION_WEEKS)


def build_patch_state(*, universe_seed: int, week: int) -> dict[str, Any]:
    pool_data = _load_pool_data()
    patch_index = patch_index_for_week(week)
    rng = random.Random(universe_seed + patch_index * 9973)
    template = _PATCH_SHIFT_TEMPLATES[patch_index % len(_PATCH_SHIFT_TEMPLATES)]
    shifts = {tag: delta for tag, delta in template}

    notes: list[str] = []
    for tag, delta in template:
        line = _PATCH_NOTES_LINES.get(tag)
        if line:
            prefix = "Buff" if delta > 0 else "Nerf"
            notes.append(f"{prefix} {tag} — {line}")

    viable_by_role: dict[str, list[str]] = {}
    by_role = _champions_by_role(pool_data)
    for role in ROLES:
        scored: list[tuple[float, str]] = []
        for champion in by_role[role]:
            score = 1.0
            for tag in champion["tags"]:
                score += shifts.get(tag, 0.0)
            score += rng.uniform(-0.04, 0.04)
            scored.append((score, champion["name"]))
        scored.sort(key=lambda item: (-item[0], item[1]))
        viable_by_role[role] = [name for _, name in scored[:18]]

    return {
        "patch_id": f"LEC-C{patch_index + 1}",
        "patch_label": f"LEC Carrière {patch_index + 1}.{week % PATCH_ROTATION_WEEKS + 1}",
        "week": week,
        "tag_shifts": shifts,
        "notes": notes,
        "viable_by_role": viable_by_role,
    }


def _generate_player_profile(
    *,
    player_name: str,
    role: Role,
    team_tags: list[str],
    viable: list[str],
    by_role_lookup: dict[str, dict[str, list[str]]],
    rng: random.Random,
) -> dict[str, Any]:
    role_champs = by_role_lookup.get(role, {})
    weighted: list[tuple[float, str]] = []
    for champion in viable:
        tags = role_champs.get(champion, [])
        overlap = sum(1 for tag in tags if tag in team_tags)
        weighted.append((overlap + rng.random() * 0.6, champion))
    weighted.sort(key=lambda item: (-item[0], item[1]))
    comfort_count = 3 + rng.randint(0, 2)
    comfort = [name for _, name in weighted[:comfort_count]]
    return {
        "player": player_name,
        "role": role,
        "comfort": comfort,
        "power": round(0.55 + rng.random() * 0.3, 3),
        "flexibility": round(0.25 + rng.random() * 0.45, 3),
        "tags": team_tags[:2],
    }


def build_team_identity(
    team_id: str,
    *,
    pool_data: dict[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    archetypes = pool_data.get("team_archetypes") or {}
    base = dict(archetypes.get(team_id) or archetypes.get("player") or {})
    tags = list(base.get("tags") or ["skirmish", "scaling"])
    return {
        "team_id": team_id,
        "label": base.get("label", "Style équilibré"),
        "tags": tags,
        "spice_chance": float(base.get("spice", 0.12)),
        "ban_bias": tags[:2],
    }


def build_team_profiles(
    team: dict[str, Any],
    *,
    identity: dict[str, Any],
    patch_state: dict[str, Any],
    pool_data: dict[str, Any],
    rng: random.Random,
) -> list[dict[str, Any]]:
    roster = team.get("roster") or {}
    by_role = _champions_by_role(pool_data)
    lookup = {
        role: {item["name"]: item["tags"] for item in items}
        for role, items in by_role.items()
    }
    viable = patch_state["viable_by_role"]
    profiles: list[dict[str, Any]] = []
    for role in ROLES:
        player_name = str(roster.get(role, role.title())).strip() or role.title()
        profiles.append(
            _generate_player_profile(
                player_name=player_name,
                role=role,
                team_tags=identity["tags"],
                viable=viable.get(role, []),
                by_role_lookup=lookup,
                rng=rng,
            )
        )
    return profiles


def generate_career_universe(
    teams: list[dict[str, Any]],
    *,
    seed: int | str | None = None,
    week: int = 1,
) -> dict[str, Any]:
    """Génère la meta carrière complète pour une saison (déterministe)."""
    universe_seed = _seed_int(seed)
    pool_data = _load_pool_data()
    patch_state = build_patch_state(universe_seed=universe_seed, week=week)

    team_identities: dict[str, dict[str, Any]] = {}
    team_profiles: dict[str, list[dict[str, Any]]] = {}

    for index, team in enumerate(teams):
        team_id = str(team.get("id", f"team-{index}"))
        team_rng = random.Random(universe_seed + index * 104729)
        identity = build_team_identity(team_id, pool_data=pool_data, rng=team_rng)
        team_identities[team_id] = identity
        team_profiles[team_id] = build_team_profiles(
            team,
            identity=identity,
            patch_state=patch_state,
            pool_data=pool_data,
            rng=team_rng,
        )

    return {
        "universe_seed": universe_seed,
        "patch": patch_state,
        "team_identities": team_identities,
        "team_profiles": team_profiles,
    }


def get_career_patch_for_week(
    universe_seed: int,
    week: int,
) -> dict[str, Any]:
    return build_patch_state(universe_seed=universe_seed, week=week)


def refresh_career_universe_week(
    universe: dict[str, Any],
    teams: list[dict[str, Any]],
    week: int,
) -> dict[str, Any]:
    """Met à jour le patch courant sans regénérer identités/profils."""
    seed = int(universe.get("universe_seed", 0))
    pool_data = _load_pool_data()
    patch_state = build_patch_state(universe_seed=seed, week=week)
    team_identities = universe.get("team_identities") or {}
    team_profiles: dict[str, list[dict[str, Any]]] = {}

    for index, team in enumerate(teams):
        team_id = str(team.get("id", f"team-{index}"))
        identity = team_identities.get(team_id) or build_team_identity(
            team_id,
            pool_data=pool_data,
            rng=random.Random(seed + index * 104729),
        )
        team_rng = random.Random(seed + index * 104729 + week * 17)
        team_profiles[team_id] = build_team_profiles(
            team,
            identity=identity,
            patch_state=patch_state,
            pool_data=pool_data,
            rng=team_rng,
        )

    return {
        **universe,
        "patch": patch_state,
        "team_profiles": team_profiles,
    }
