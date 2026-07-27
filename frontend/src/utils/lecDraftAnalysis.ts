import type { DraftPick, Team } from "../types/draft";
import type { LecCareerPatch } from "../types/lec";

export interface LecDraftAnalysis {
  playerWinProbability: number;
  playerScore: number;
  opponentScore: number;
  highlights: string[];
}

function picksForSide(
  playerSide: Team,
  bluePicks: DraftPick[],
  redPicks: DraftPick[],
): { playerPicks: DraftPick[]; opponentPicks: DraftPick[] } {
  return playerSide === "blue"
    ? { playerPicks: bluePicks, opponentPicks: redPicks }
    : { playerPicks: redPicks, opponentPicks: bluePicks };
}

function championMetaScore(champion: string, role: string | undefined, patch: LecCareerPatch): number {
  if (!role) {
    return 0.45;
  }
  const viable = patch.viable_by_role[role] ?? [];
  const index = viable.indexOf(champion);
  if (index === -1) {
    return 0.32;
  }
  return 0.55 + (1 - index / Math.max(viable.length, 1)) * 0.38;
}

function teamDraftScore(picks: DraftPick[], patch: LecCareerPatch): number {
  if (!picks.length) {
    return 0.5;
  }
  const total = picks.reduce(
    (sum, pick) => sum + championMetaScore(pick.champion, pick.role, patch),
    0,
  );
  return total / picks.length;
}

export function analyzeCareerDraft({
  playerSide,
  bluePicks,
  redPicks,
  patch,
}: {
  playerSide: Team;
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  patch: LecCareerPatch;
}): LecDraftAnalysis {
  const { playerPicks, opponentPicks } = picksForSide(playerSide, bluePicks, redPicks);
  const playerScore = teamDraftScore(playerPicks, patch);
  const opponentScore = teamDraftScore(opponentPicks, patch);
  const delta = playerScore - opponentScore;
  const playerWinProbability = Math.min(0.78, Math.max(0.22, 0.5 + delta * 0.85));

  const highlights: string[] = [];
  const inVoguePlayer = playerPicks.filter(
    (pick) => pick.role && (patch.viable_by_role[pick.role]?.slice(0, 5).includes(pick.champion) ?? false),
  );
  const offMetaPlayer = playerPicks.filter(
    (pick) => pick.role && !(patch.viable_by_role[pick.role]?.includes(pick.champion) ?? true),
  );

  if (inVoguePlayer.length >= 3) {
    highlights.push("Ta comp colle bien à la meta du patch.");
  } else if (inVoguePlayer.length >= 1) {
    highlights.push(`${inVoguePlayer.length} pick(s) en vogue ce patch.`);
  }
  if (offMetaPlayer.length >= 2) {
    highlights.push("Plusieurs picks hors meta — edge réduit.");
  }
  if (delta > 0.08) {
    highlights.push("Avantage draft estimé sur l'adversaire.");
  } else if (delta < -0.08) {
    highlights.push("Draft adverse mieux alignée avec la meta.");
  } else {
    highlights.push("Draft équilibrée — match serré attendu.");
  }

  return {
    playerWinProbability,
    playerScore,
    opponentScore,
    highlights,
  };
}

export function resolveCareerMatch(playerWinProbability: number): boolean {
  return Math.random() < playerWinProbability;
}

export function inVogueChampionsByRole(patch: LecCareerPatch, topN = 5): Record<string, string[]> {
  const result: Record<string, string[]> = {};
  for (const [role, champions] of Object.entries(patch.viable_by_role)) {
    result[role] = champions.slice(0, topN);
  }
  return result;
}
