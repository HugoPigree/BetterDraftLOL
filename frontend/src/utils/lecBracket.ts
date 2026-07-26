import type { BracketMatch } from "../types/worlds";
import type { LecTeam } from "../types/lec";

export function hydrateLecPlayoffs(
  bracket: BracketMatch[],
  playerTeamId = "player",
): BracketMatch[] {
  const winners = new Map<string, LecTeam | null>();
  for (const match of bracket) {
    if (!match.winner_id) {
      continue;
    }
    const winner =
      match.team_a.team?.id === match.winner_id
        ? match.team_a.team
        : match.team_b.team?.id === match.winner_id
          ? match.team_b.team
          : null;
    winners.set(match.id, winner ?? null);
  }

  return bracket.map((match) => {
    const teamA =
      match.team_a.team ??
      (match.team_a.source_match_id
        ? winners.get(match.team_a.source_match_id) ?? null
        : null);
    const teamB =
      match.team_b.team ??
      (match.team_b.source_match_id
        ? winners.get(match.team_b.source_match_id) ?? null
        : null);

    return {
      ...match,
      team_a: { ...match.team_a, team: teamA },
      team_b: { ...match.team_b, team: teamB },
    };
  });
}

export function getPlayerPlayoffMatch(
  bracket: BracketMatch[],
  playerTeamId = "player",
): BracketMatch | null {
  for (const match of bracket) {
    if (match.winner_id) {
      continue;
    }
    const teamAId = match.team_a.team?.id;
    const teamBId = match.team_b.team?.id;
    if (teamAId === playerTeamId || teamBId === playerTeamId) {
      if (teamAId && teamBId) {
        return match;
      }
    }
  }
  return null;
}

export function recordPlayoffWinner(
  bracket: BracketMatch[],
  matchId: string,
  winnerId: string,
): BracketMatch[] {
  return bracket.map((match) =>
    match.id === matchId ? { ...match, winner_id: winnerId } : match,
  );
}

export function resolveNpcPlayoffMatches(
  bracket: BracketMatch[],
  playerTeamId = "player",
): BracketMatch[] {
  let updated = [...bracket];
  let changed = true;

  while (changed) {
    changed = false;
    const hydrated = hydrateLecPlayoffs(updated, playerTeamId);

    for (const match of hydrated) {
      if (match.winner_id) {
        continue;
      }
      const teamA = match.team_a.team;
      const teamB = match.team_b.team;
      if (!teamA || !teamB) {
        continue;
      }
      if (teamA.id === playerTeamId || teamB.id === playerTeamId) {
        continue;
      }

      const powerA = teamA.power_rating ?? 0.5;
      const powerB = teamB.power_rating ?? 0.5;
      const winnerId =
        Math.random() < 0.5 + (powerA - powerB) * 0.45 ? teamA.id : teamB.id;
      updated = recordPlayoffWinner(updated, match.id, winnerId);
      changed = true;
    }
  }

  return updated;
}

export function playerQualifiedForWorldsFromPlayoffs(
  bracket: BracketMatch[],
  standingsRank: number,
): boolean {
  if (standingsRank <= 3) {
    return true;
  }
  const final = bracket.find((match) => match.round === "final");
  if (!final?.winner_id) {
    return false;
  }
  return final.winner_id === "player";
}
