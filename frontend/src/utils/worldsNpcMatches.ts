import type { BracketMatch, WorldsRound } from "../types/worlds";
import { hydrateBracket, recordMatchWinner } from "./worldsBracket";

const REGION_POWER: Record<string, number> = {
  LCK: 0.58,
  LPL: 0.57,
  LEC: 0.52,
  CUSTOM: 0.5,
};

function teamPower(team: { region: string }): number {
  return REGION_POWER[team.region] ?? 0.5;
}

function pickNpcWinner(
  teamA: { id: string; region: string },
  teamB: { id: string; region: string },
  matchId: string,
): string {
  const powerA = teamPower(teamA);
  const powerB = teamPower(teamB);
  const total = powerA + powerB;
  let hash = 0;
  for (const char of matchId) {
    hash = (hash * 31 + char.charCodeAt(0)) % 997;
  }
  const roll = (hash % 1000) / 1000;
  return roll < powerA / total ? teamA.id : teamB.id;
}

/** Résout uniquement les matchs NPC d'un round donné (sans le match du joueur). */
export function autoResolveNpcRound(
  bracket: BracketMatch[],
  round: WorldsRound,
  playerTeamId: string,
): BracketMatch[] {
  let updated = [...bracket];
  const hydrated = hydrateBracket(updated);

  for (const match of hydrated) {
    if (match.round !== round || match.winner_id) {
      continue;
    }
    const teamA = match.team_a.team;
    const teamB = match.team_b.team;
    if (!teamA || !teamB) {
      continue;
    }
    const involvesPlayer = teamA.id === playerTeamId || teamB.id === playerTeamId;
    if (involvesPlayer) {
      continue;
    }
    const winnerId = pickNpcWinner(teamA, teamB, match.id);
    updated = recordMatchWinner(updated, match.id, winnerId);
  }

  return updated;
}

/** Résout les matchs NPC nécessaires pour débloquer le prochain match du joueur. */
export function prepareBracketForPlayer(
  bracket: BracketMatch[],
  playerTeamId: string,
): BracketMatch[] {
  let updated = [...bracket];
  for (const round of ["quarter", "semi", "final"] as WorldsRound[]) {
    updated = autoResolveNpcRound(updated, round, playerTeamId);
    const hydrated = hydrateBracket(updated);
    const playerMatch = hydrated.find(
      (match) =>
        match.round === round &&
        !match.winner_id &&
        (match.team_a.team?.id === playerTeamId || match.team_b.team?.id === playerTeamId),
    );
    if (playerMatch) {
      const nameA = playerMatch.team_a.team?.name;
      const nameB = playerMatch.team_b.team?.name;
      if (nameA && nameB) {
        break;
      }
    }
  }
  return updated;
}

/** Après victoire du joueur, résout le reste du round courant. */
export function resolveRoundAfterPlayerWin(
  bracket: BracketMatch[],
  round: WorldsRound,
  playerTeamId: string,
): BracketMatch[] {
  return autoResolveNpcRound(bracket, round, playerTeamId);
}
