import { useEffect, useMemo, useState } from "react";
import type { DraftPick, Team } from "../types/draft";
import type {
  PredictionMode,
  RetrospectiveBanSuggestion,
  RetrospectivePickSuggestion,
} from "../types/predict";
import { suggestRetrospectiveBan, suggestRetrospectivePick } from "../services/api";
import { getAvailableChampions } from "../utils/draftTeamBuilder";
import { resolveLoserProbability, resolveLoserSide } from "../utils/resolveLoserSide";

export interface RetrospectiveAdviceState {
  loading: boolean;
  error: string | null;
  loserSide: Team;
  loserProbability: number;
  pickSuggestions: RetrospectivePickSuggestion[];
  banSuggestions: RetrospectiveBanSuggestion[];
}

export function useRetrospectiveAdvice(
  enabled: boolean,
  bluePicks: DraftPick[],
  redPicks: DraftPick[],
  blueWinProbability: number,
  redWinProbability: number,
  patch: string,
  predictionMode: PredictionMode,
  champions: string[],
  usedChampions: string[],
): RetrospectiveAdviceState {
  const loserSide = useMemo(
    () => resolveLoserSide(blueWinProbability, redWinProbability),
    [blueWinProbability, redWinProbability],
  );

  const loserProbability = useMemo(
    () => resolveLoserProbability(blueWinProbability, redWinProbability, loserSide),
    [blueWinProbability, redWinProbability, loserSide],
  );

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pickSuggestions, setPickSuggestions] = useState<RetrospectivePickSuggestion[]>([]);
  const [banSuggestions, setBanSuggestions] = useState<RetrospectiveBanSuggestion[]>([]);

  useEffect(() => {
    if (!enabled || champions.length === 0) {
      setLoading(false);
      setError(null);
      setPickSuggestions([]);
      setBanSuggestions([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const available = getAvailableChampions(champions, usedChampions);
    const teamPicks = loserSide === "blue" ? bluePicks : redPicks;
    const opponentPicks = loserSide === "blue" ? redPicks : bluePicks;

    Promise.all([
      suggestRetrospectivePick(
        loserSide,
        teamPicks,
        opponentPicks,
        patch,
        available,
        predictionMode,
      ),
      suggestRetrospectiveBan(
        loserSide,
        teamPicks,
        opponentPicks,
        patch,
        available,
        predictionMode,
      ),
    ])
      .then(([pickResult, banResult]) => {
        if (cancelled) {
          return;
        }
        setPickSuggestions(pickResult.suggestions);
        setBanSuggestions(banResult.suggestions);
      })
      .catch((fetchError: Error) => {
        if (!cancelled) {
          setPickSuggestions([]);
          setBanSuggestions([]);
          setError(fetchError.message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [
    enabled,
    loserSide,
    bluePicks,
    redPicks,
    patch,
    predictionMode,
    champions,
    usedChampions,
  ]);

  return {
    loading,
    error,
    loserSide,
    loserProbability,
    pickSuggestions,
    banSuggestions,
  };
}
