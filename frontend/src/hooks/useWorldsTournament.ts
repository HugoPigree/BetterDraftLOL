import { useCallback, useMemo, useState } from "react";
import type { DraftPreferences } from "../types/draft";
import type {
  BracketMatch,
  WorldsPhase,
  WorldsRoster,
  WorldsTeam,
} from "../types/worlds";
import {
  getPlayerNextMatch,
  hydrateBracket,
  isPlayerChampion,
  isPlayerEliminated,
  opponentForPlayer,
  playerIsTeamA,
  recordMatchWinner,
} from "../utils/worldsBracket";
import {
  prepareBracketForPlayer,
  resolveRoundAfterPlayerWin,
} from "../utils/worldsNpcMatches";
import { startWorldsTournament } from "../services/api";

const DEFAULT_DRAFT_PREFERENCES: DraftPreferences = {
  playerSide: "blue",
  pickOrder: "first",
};

export function useWorldsTournament() {
  const [phase, setPhase] = useState<WorldsPhase>("setup");
  const [playerTeam, setPlayerTeam] = useState<WorldsTeam | null>(null);
  const [opponentTeams, setOpponentTeams] = useState<WorldsTeam[]>([]);
  const [bracket, setBracket] = useState<BracketMatch[]>([]);
  const [currentMatchId, setCurrentMatchId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftPreferences, setDraftPreferences] = useState<DraftPreferences>(
    DEFAULT_DRAFT_PREFERENCES,
  );

  const hydratedBracket = useMemo(() => hydrateBracket(bracket), [bracket]);

  const currentMatch = useMemo(() => {
    if (!currentMatchId) {
      return null;
    }
    return hydratedBracket.find((match) => match.id === currentMatchId) ?? null;
  }, [currentMatchId, hydratedBracket]);

  const currentOpponent = useMemo(() => {
    if (!currentMatch || !playerTeam) {
      return null;
    }
    return opponentForPlayer(currentMatch, playerTeam.id);
  }, [currentMatch, playerTeam]);

  const playerSide = draftPreferences.playerSide;

  const startTournament = useCallback(
    async (teamName: string, coachName: string, roster: WorldsRoster) => {
      setLoading(true);
      setError(null);
      try {
        const response = await startWorldsTournament(teamName, coachName, roster);
        setPlayerTeam(response.player_team);
        setOpponentTeams(response.opponent_teams);
        setBracket(response.bracket);
        setPhase("bracket");
      } catch (startError) {
        setError(
          startError instanceof Error
            ? startError.message
            : "Impossible de lancer le tournoi Worlds",
        );
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  const openNextPlayerMatch = useCallback(() => {
    if (!playerTeam) {
      return;
    }
    const prepared = prepareBracketForPlayer(bracket, playerTeam.id);
    setBracket(prepared);
    const nextMatch = getPlayerNextMatch(prepared, playerTeam.id);
    if (!nextMatch) {
      if (isPlayerChampion(prepared, playerTeam.id)) {
        setPhase("champion");
      } else if (isPlayerEliminated(prepared, playerTeam.id)) {
        setPhase("eliminated");
      }
      return;
    }
    setCurrentMatchId(nextMatch.id);
    const bracketSide = playerIsTeamA(nextMatch, playerTeam.id) ? "blue" : "red";
    setDraftPreferences({
      playerSide: bracketSide,
      pickOrder: bracketSide === "blue" ? "first" : "last",
    });
    setPhase("matchIntro");
  }, [bracket, playerTeam]);

  const beginDraft = useCallback(() => {
    setPhase("drafting");
  }, []);

  const showDraftResult = useCallback(() => {
    setPhase("draftResult");
  }, []);

  const beginSimulation = useCallback(() => {
    setPhase("simulating");
  }, []);

  const finishMatch = useCallback(
    (playerWon: boolean) => {
      if (!currentMatch || !playerTeam || !currentOpponent) {
        return;
      }
      const winnerId = playerWon ? playerTeam.id : currentOpponent.id;
      let updated = recordMatchWinner(bracket, currentMatch.id, winnerId);
      if (playerWon) {
        updated = resolveRoundAfterPlayerWin(updated, currentMatch.round, playerTeam.id);
      }
      setBracket(updated);
      setPhase("matchResult");
    },
    [bracket, currentMatch, currentOpponent, playerTeam],
  );

  const returnToBracket = useCallback(() => {
    setCurrentMatchId(null);
    if (!playerTeam) {
      setPhase("setup");
      return;
    }
    if (isPlayerChampion(bracket, playerTeam.id)) {
      setPhase("champion");
      return;
    }
    if (isPlayerEliminated(bracket, playerTeam.id)) {
      setPhase("eliminated");
      return;
    }
    setPhase("bracket");
  }, [bracket, playerTeam]);

  const resetTournament = useCallback(() => {
    setPhase("setup");
    setPlayerTeam(null);
    setOpponentTeams([]);
    setBracket([]);
    setCurrentMatchId(null);
    setDraftPreferences(DEFAULT_DRAFT_PREFERENCES);
    setError(null);
  }, []);

  return {
    phase,
    setPhase,
    playerTeam,
    opponentTeams,
    bracket: hydratedBracket,
    currentMatch,
    currentOpponent,
    playerSide,
    draftPreferences,
    setDraftPreferences,
    loading,
    error,
    startTournament,
    openNextPlayerMatch,
    beginDraft,
    showDraftResult,
    beginSimulation,
    finishMatch,
    returnToBracket,
    resetTournament,
  };
}
