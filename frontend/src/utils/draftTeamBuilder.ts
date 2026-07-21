import { ROLES } from "../hooks/useDraftState";
import type { DraftPick, Role, Team } from "../types/draft";

export function getAvailableChampions(
  allChampions: string[],
  usedChampions: string[],
): string[] {
  const used = new Set(usedChampions.map((name) => name.toLowerCase()));
  return allChampions.filter((name) => !used.has(name.toLowerCase()));
}

export function getRemainingRoles(picks: DraftPick[]): Role[] {
  const filled = new Set(picks.map((pick) => pick.role));
  return ROLES.filter((role) => !filled.has(role));
}

function championCanPlayRole(
  champion: string,
  role: Role,
  championPositions: Record<string, Role[]>,
): boolean {
  return championPositions[champion]?.includes(role) ?? false;
}

function pickFillerForRole(
  role: Role,
  candidates: string[],
  championPositions: Record<string, Role[]>,
  reserved: Set<string>,
): string {
  for (const champion of [...candidates].sort((a, b) => a.localeCompare(b))) {
    if (reserved.has(champion.toLowerCase())) {
      continue;
    }
    if (championCanPlayRole(champion, role, championPositions)) {
      return champion;
    }
  }

  const fallback = candidates.find((champion) => !reserved.has(champion.toLowerCase()));
  if (!fallback) {
    throw new Error("Pas assez de champions disponibles pour simuler la draft");
  }
  return fallback;
}

export function buildPaddedTeam(
  picks: DraftPick[],
  allChampions: string[],
  championPositions: Record<string, Role[]>,
  usedChampions: string[],
): DraftPick[] {
  const byRole = new Map<Role, string>();
  for (const pick of picks) {
    byRole.set(pick.role, pick.champion);
  }

  const available = getAvailableChampions(allChampions, usedChampions);
  const reserved = new Set(usedChampions.map((name) => name.toLowerCase()));
  const team: DraftPick[] = [];

  for (const role of ROLES) {
    const existing = byRole.get(role);
    if (existing) {
      team.push({ role, champion: existing });
      continue;
    }

    const filler = pickFillerForRole(role, available, championPositions, reserved);
    team.push({ role, champion: filler });
    reserved.add(filler.toLowerCase());
  }

  return team;
}

export function opponentTeam(draftTeam: Team): Team {
  return draftTeam === "blue" ? "red" : "blue";
}

export function teamPicksForSide(draft: {
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
}, side: Team): DraftPick[] {
  return side === "blue" ? draft.bluePicks : draft.redPicks;
}
