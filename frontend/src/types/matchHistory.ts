import type { MatchSimulationResult } from "../types/worlds";
import type { PredictResponse } from "../types/predict";
import type { DraftPick } from "../types/draft";

export interface MatchHistorySummary {
  playerTeamName: string;
  opponentTeamName: string;
  playerSide: "blue" | "red";
  playerWon: boolean;
  draftPrediction: PredictResponse | null;
  simulation: MatchSimulationResult | null;
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
}
