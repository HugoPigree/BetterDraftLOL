import type { DraftPick, Role } from "../types/draft";
import type { LecCareerPatch, LecPlayerProfile, LecTeamIdentity } from "../types/lec";
import { LEC_ROLES } from "../types/lec";

const SIGNATURE_BONUS = 0.34;
const COMFORT_BONUS = 0.16;

function profileForRole(profiles: LecPlayerProfile[], role: Role): LecPlayerProfile | undefined {
  return profiles.find((profile) => profile.role === role);
}

function vogueBonus(champion: string, role: Role, patch: LecCareerPatch): number {
  const viable = patch.viable_by_role[role] ?? [];
  const index = viable.indexOf(champion);
  if (index === -1) {
    return -0.38;
  }
  return 0.14 + (1 - index / Math.max(viable.length, 1)) * 0.24;
}

function preferenceBonus(champion: string, profile: LecPlayerProfile | undefined): number {
  if (!profile) {
    return 0;
  }
  const power = profile.power ?? 0.65;
  if (profile.signature_picks?.includes(champion)) {
    return SIGNATURE_BONUS * power;
  }
  if (profile.comfort?.includes(champion)) {
    return COMFORT_BONUS * power;
  }
  return 0;
}

function scoreCareerPick(
  champion: string,
  role: Role,
  patch: LecCareerPatch,
  profile: LecPlayerProfile | undefined,
  identity?: LecTeamIdentity,
): number {
  let score = vogueBonus(champion, role, patch) + preferenceBonus(champion, profile);
  if (identity?.tags?.length) {
    score += identity.tags.length * 0.01;
  }
  return score;
}

function scoreCareerBan(
  champion: string,
  patch: LecCareerPatch,
  opponentProfiles: LecPlayerProfile[],
): number {
  let score = 0;
  for (const role of LEC_ROLES) {
    score = Math.max(score, vogueBonus(champion, role, patch));
  }
  for (const profile of opponentProfiles) {
    if (profile.signature_picks?.includes(champion)) {
      score += 0.32;
    } else if (profile.comfort?.includes(champion)) {
      score += 0.16;
    }
  }
  return score;
}

export function suggestCareerDraftChampion({
  actionType,
  available,
  championPositions,
  patch,
  teamProfiles,
  teamIdentity,
  opponentProfiles = [],
}: {
  actionType: "ban" | "pick";
  available: string[];
  championPositions: Record<string, Role[]>;
  patch: LecCareerPatch;
  teamProfiles: LecPlayerProfile[];
  teamIdentity?: LecTeamIdentity;
  opponentProfiles?: LecPlayerProfile[];
}): string | null {
  if (!available.length) {
    return null;
  }

  if (actionType === "ban") {
    let best = available[0];
    let bestScore = Number.NEGATIVE_INFINITY;
    for (const champion of available) {
      const score = scoreCareerBan(champion, patch, opponentProfiles);
      if (score > bestScore) {
        bestScore = score;
        best = champion;
      }
    }
    return best;
  }

  let best: string | null = null;
  let bestScore = Number.NEGATIVE_INFINITY;
  for (const champion of available) {
    const roles = championPositions[champion] ?? [];
    for (const role of roles) {
      if (!LEC_ROLES.includes(role)) {
        continue;
      }
      const score = scoreCareerPick(
        champion,
        role,
        patch,
        profileForRole(teamProfiles, role),
        teamIdentity,
      );
      if (score > bestScore) {
        bestScore = score;
        best = champion;
      }
    }
  }

  return best ?? available[0];
}

export function inVogueChampionSet(patch: LecCareerPatch, topN = 5): Set<string> {
  const champions = new Set<string>();
  for (const pool of Object.values(patch.viable_by_role)) {
    for (const champion of pool.slice(0, topN)) {
      champions.add(champion);
    }
  }
  return champions;
}

export function scorePlayerDraftPicks(picks: DraftPick[], patch: LecCareerPatch): number {
  if (!picks.length) {
    return 0.5;
  }
  const total = picks.reduce((sum, pick) => {
    if (!pick.role) {
      return sum + 0.4;
    }
    return sum + Math.max(0, vogueBonus(pick.champion, pick.role as Role, patch) + 0.5);
  }, 0);
  return total / picks.length;
}
