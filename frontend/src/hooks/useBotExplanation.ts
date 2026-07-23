import { useCallback, useState } from "react";
import type { DraftPick, Team } from "../types/draft";
import type { PredictionMode } from "../types/predict";
import {
  fetchBotExplanation,
  type BotExplanationStep,
} from "../services/api";

interface UseBotExplanationOptions {
  botSide: Team;
  botPicks: DraftPick[];
  opponentPicks: DraftPick[];
  patch: string;
  mode?: PredictionMode;
  enabled: boolean;
}

export function useBotExplanation({
  botSide,
  botPicks,
  opponentPicks,
  patch,
  mode = "pro",
  enabled,
}: UseBotExplanationOptions) {
  const [active, setActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<BotExplanationStep[]>([]);
  const [stepIndex, setStepIndex] = useState(0);

  const currentStep = active && steps.length > 0 ? steps[stepIndex] ?? null : null;
  const isLastStep = stepIndex >= steps.length - 1;
  const highlightedChampion =
    currentStep?.champion && currentStep.champion.length > 0
      ? currentStep.champion
      : null;

  const start = useCallback(async () => {
    if (!enabled || botPicks.length === 0) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetchBotExplanation(botPicks, opponentPicks, patch, mode);
      if (!response.steps.length) {
        throw new Error("Aucune explication renvoyée");
      }
      setSteps(response.steps);
      setStepIndex(0);
      setActive(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Explication impossible");
      setActive(false);
      setSteps([]);
    } finally {
      setLoading(false);
    }
  }, [enabled, botPicks, opponentPicks, patch, mode]);

  const next = useCallback(() => {
    setStepIndex((index) => {
      if (index >= steps.length - 1) {
        setActive(false);
        return 0;
      }
      return index + 1;
    });
  }, [steps.length]);

  const skipAll = useCallback(() => {
    setActive(false);
    setStepIndex(0);
    setError(null);
  }, []);

  return {
    active,
    loading,
    error,
    currentStep,
    stepIndex,
    stepCount: steps.length,
    isLastStep,
    highlightedChampion,
    highlightedSide: botSide,
    start,
    next,
    skipAll,
  };
}
