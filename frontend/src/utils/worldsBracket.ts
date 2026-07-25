import type { BracketMatch, BracketTeamSlot, WorldsRound, WorldsTeam } from "../types/worlds";

function resolveWinnerTeam(match: BracketMatch): WorldsTeam | null {
  if (!match.winner_id) {
    return null;
  }
  if (match.team_a.team?.id === match.winner_id) {
    return match.team_a.team;
  }
  if (match.team_b.team?.id === match.winner_id) {
    return match.team_b.team;
  }
  return null;
}

export function bracketById(bracket: BracketMatch[]): Record<string, BracketMatch> {
  return Object.fromEntries(bracket.map((match) => [match.id, { ...match }]));
}

/** Hydrate uniquement les slots dont le match source est terminé. */
export function hydrateBracket(bracket: BracketMatch[]): BracketMatch[] {
  const byId = bracketById(bracket);

  for (const match of Object.values(byId)) {
    if (!match.team_a.team && match.team_a.source_match_id) {
      const source = byId[match.team_a.source_match_id];
      const winner = source?.winner_id ? resolveWinnerTeam(source) : null;
      match.team_a = { ...match.team_a, team: winner };
    }
    if (!match.team_b.team && match.team_b.source_match_id) {
      const source = byId[match.team_b.source_match_id];
      const winner = source?.winner_id ? resolveWinnerTeam(source) : null;
      match.team_b = { ...match.team_b, team: winner };
    }
  }

  return Object.values(byId);
}

export function displayTeamName(
  slot: BracketTeamSlot,
  byId: Record<string, BracketMatch>,
): string {
  if (slot.team) {
    return slot.team.name;
  }
  if (slot.source_match_id) {
    const source = byId[slot.source_match_id];
    if (!source?.winner_id) {
      return "TBD";
    }
    const winner = resolveWinnerTeam(source);
    return winner?.name ?? "TBD";
  }
  return "TBD";
}

export function isSlotLocked(slot: BracketTeamSlot, byId: Record<string, BracketMatch>): boolean {
  if (slot.team) {
    return false;
  }
  if (!slot.source_match_id) {
    return false;
  }
  const source = byId[slot.source_match_id];
  return !source?.winner_id;
}

export function getMatchesByRound(
  bracket: BracketMatch[],
  round: WorldsRound,
): BracketMatch[] {
  const order = ["qf1", "qf2", "qf3", "qf4", "sf1", "sf2", "final"];
  return hydrateBracket(bracket)
    .filter((match) => match.round === round)
    .sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
}

export function getReadyMatches(bracket: BracketMatch[]): BracketMatch[] {
  const byId = bracketById(bracket);
  return hydrateBracket(bracket).filter((match) => {
    const nameA = displayTeamName(match.team_a, byId);
    const nameB = displayTeamName(match.team_b, byId);
    return nameA !== "TBD" && nameB !== "TBD" && !match.winner_id;
  });
}

export function getPlayerNextMatch(
  bracket: BracketMatch[],
  playerTeamId: string,
): BracketMatch | null {
  const ready = getReadyMatches(bracket);
  return (
    ready.find((match) => {
      const hydrated = hydrateBracket(bracket).find((item) => item.id === match.id);
      if (!hydrated) {
        return false;
      }
      return (
        hydrated.team_a.team?.id === playerTeamId || hydrated.team_b.team?.id === playerTeamId
      );
    }) ?? null
  );
}

export function recordMatchWinner(
  bracket: BracketMatch[],
  matchId: string,
  winnerId: string,
): BracketMatch[] {
  return bracket.map((match) =>
    match.id === matchId ? { ...match, winner_id: winnerId } : match,
  );
}

export function playerRoundComplete(
  bracket: BracketMatch[],
  playerTeamId: string,
  round: WorldsRound,
): boolean {
  const hydrated = hydrateBracket(bracket);
  const playerMatch = hydrated.find(
    (match) =>
      match.round === round &&
      (match.team_a.team?.id === playerTeamId || match.team_b.team?.id === playerTeamId),
  );
  return Boolean(playerMatch?.winner_id);
}

export function shouldRevealRound(
  bracket: BracketMatch[],
  playerTeamId: string,
  round: WorldsRound,
): boolean {
  if (round === "quarter") {
    return true;
  }
  if (round === "semi") {
    return playerRoundComplete(bracket, playerTeamId, "quarter");
  }
  return playerRoundComplete(bracket, playerTeamId, "semi");
}

export function isPlayerEliminated(
  bracket: BracketMatch[],
  playerTeamId: string,
): boolean {
  const hydrated = hydrateBracket(bracket);
  const playerLoss = hydrated.find(
    (match) =>
      match.winner_id &&
      match.winner_id !== playerTeamId &&
      (match.team_a.team?.id === playerTeamId || match.team_b.team?.id === playerTeamId),
  );
  return Boolean(playerLoss);
}

export function isPlayerChampion(
  bracket: BracketMatch[],
  playerTeamId: string,
): boolean {
  const finalMatch = hydrateBracket(bracket).find((match) => match.round === "final");
  return finalMatch?.winner_id === playerTeamId;
}

export function opponentForPlayer(
  match: BracketMatch,
  playerTeamId: string,
): WorldsTeam | null {
  const hydrated = hydrateBracket([match])[0];
  if (hydrated.team_a.team?.id === playerTeamId) {
    return hydrated.team_b.team;
  }
  if (hydrated.team_b.team?.id === playerTeamId) {
    return hydrated.team_a.team;
  }
  return null;
}

export function playerIsTeamA(match: BracketMatch, playerTeamId: string): boolean {
  const hydrated = hydrateBracket([match])[0];
  return hydrated.team_a.team?.id === playerTeamId;
}

export function getMatchById(
  bracket: BracketMatch[],
  matchId: string,
): BracketMatch | undefined {
  return hydrateBracket(bracket).find((match) => match.id === matchId);
}
