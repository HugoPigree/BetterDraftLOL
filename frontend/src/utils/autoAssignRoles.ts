import { ROLES } from "../hooks/useDraftState";
import type { DraftPick, Role } from "../types/draft";

export interface RoleValidation {
  valid: boolean;
  duplicateRoles: Role[];
  message: string | null;
}

const ROLE_LABELS: Record<Role, string> = {
  TOP: "Top",
  JUNGLE: "Jungle",
  MIDDLE: "Mid",
  BOTTOM: "ADC",
  UTILITY: "Support",
};

function championCanPlayRole(
  champion: string,
  role: Role,
  championPositions: Record<string, Role[]>,
): boolean {
  return championPositions[champion]?.includes(role) ?? false;
}

function scoreChampionForRole(
  champion: string,
  role: Role,
  championPositions: Record<string, Role[]>,
): number {
  const positions = championPositions[champion] ?? [];
  if (!positions.includes(role)) {
    return -1;
  }
  if (positions.length === 1) {
    return 3;
  }
  if (positions[0] === role) {
    return 2;
  }
  return 1;
}

/** Assign each champion to a unique role using Meraki position data. */
export function autoAssignTeamRoles(
  champions: string[],
  championPositions: Record<string, Role[]>,
): DraftPick[] {
  if (champions.length !== ROLES.length) {
    throw new Error(`Expected ${ROLES.length} champions, got ${champions.length}`);
  }

  const assigned = new Map<Role, string>();
  const remaining = new Set(champions);

  for (const champion of champions) {
    const positions = (championPositions[champion] ?? []).filter((role) => ROLES.includes(role));
    const openRoles = ROLES.filter((role) => !assigned.has(role));
    const fitting = openRoles.filter((role) => positions.includes(role));
    if (fitting.length === 1) {
      assigned.set(fitting[0], champion);
      remaining.delete(champion);
    }
  }

  for (const role of ROLES) {
    if (assigned.has(role)) {
      continue;
    }

    let bestChampion: string | null = null;
    let bestScore = -2;

    for (const champion of remaining) {
      const score = scoreChampionForRole(champion, role, championPositions);
      if (score > bestScore) {
        bestScore = score;
        bestChampion = champion;
      }
    }

    if (!bestChampion) {
      bestChampion = [...remaining][0] ?? null;
    }

    if (!bestChampion) {
      throw new Error("Unable to assign roles to team");
    }

    assigned.set(role, bestChampion);
    remaining.delete(bestChampion);
  }

  return ROLES.map((role) => ({
    role,
    champion: assigned.get(role)!,
  }));
}

/** Keep slot order (index = role) while syncing role labels. */
export function syncPickRolesBySlotOrder(picks: DraftPick[]): DraftPick[] {
  return picks.map((pick, index) => ({
    champion: pick.champion,
    role: ROLES[index],
  }));
}

export function validateTeamRoles(picks: DraftPick[]): RoleValidation {
  if (picks.length !== ROLES.length) {
    return {
      valid: false,
      duplicateRoles: [],
      message: `Assignez ${ROLES.length} champions (${picks.length}/${ROLES.length}).`,
    };
  }

  const roleCounts = new Map<Role, number>();
  for (const pick of picks) {
    roleCounts.set(pick.role, (roleCounts.get(pick.role) ?? 0) + 1);
  }

  const duplicateRoles = ROLES.filter((role) => (roleCounts.get(role) ?? 0) > 1);
  if (duplicateRoles.length > 0) {
    const labels = duplicateRoles.map((role) => ROLE_LABELS[role]).join(", ");
    return {
      valid: false,
      duplicateRoles,
      message: `Rôles en double : ${labels}. Glissez les champions pour corriger.`,
    };
  }

  const missingRoles = ROLES.filter((role) => (roleCounts.get(role) ?? 0) === 0);
  if (missingRoles.length > 0) {
    const labels = missingRoles.map((role) => ROLE_LABELS[role]).join(", ");
    return {
      valid: false,
      duplicateRoles: [],
      message: `Rôles manquants : ${labels}.`,
    };
  }

  return { valid: true, duplicateRoles: [], message: null };
}

export function getMerakiMismatchWarnings(
  picks: DraftPick[],
  championPositions: Record<string, Role[]>,
): string[] {
  return picks
    .filter((pick) => !championCanPlayRole(pick.champion, pick.role, championPositions))
    .map(
      (pick) =>
        `${pick.champion} n'est pas typiquement joué en ${ROLE_LABELS[pick.role]} (Meraki).`,
    );
}
