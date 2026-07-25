import { useEffect, useState } from "react";
import type { MatchSimulationResult } from "../types/worlds";
import type { PredictResponse } from "../types/predict";
import type { Team } from "../types/draft";

interface MatchSimulationProps {
  loading: boolean;
  error: string | null;
  result: MatchSimulationResult | null;
  playerTeamName: string;
  opponentTeamName: string;
  playerSide: Team;
  draftPrediction: PredictResponse | null;
  onComplete: (playerWins: boolean) => void;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

const PHASE_LABELS: Record<string, string> = {
  early: "Early game",
  mid: "Mid game",
  late: "Late game",
};

export function MatchSimulation({
  loading,
  error,
  result,
  playerTeamName,
  opponentTeamName,
  playerSide,
  draftPrediction,
  onComplete,
}: MatchSimulationProps) {
  const [visibleEvents, setVisibleEvents] = useState(0);
  const [finished, setFinished] = useState(false);

  const playerDraftWin = draftPrediction
    ? playerSide === "blue"
      ? draftPrediction.blue_win_probability
      : draftPrediction.red_win_probability
    : null;

  useEffect(() => {
    if (!result) {
      return;
    }
    setVisibleEvents(0);
    setFinished(false);
    const timers: number[] = [];
    result.events.forEach((_event, index) => {
      timers.push(
        window.setTimeout(() => {
          setVisibleEvents(index + 1);
        }, (index + 1) * 1100),
      );
    });
    timers.push(
      window.setTimeout(() => {
        setFinished(true);
      }, result.events.length * 1100 + 800),
    );
    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [result]);

  useEffect(() => {
    if (finished && result) {
      const timer = window.setTimeout(() => onComplete(result.player_wins), 1400);
      return () => window.clearTimeout(timer);
    }
  }, [finished, onComplete, result]);

  return (
    <div className="worlds-screen worlds-screen--center worlds-simulation">
      <div className="match-simulation">
        <p className="match-simulation__eyebrow">Worlds · Simulation live</p>
        <h2>
          {playerTeamName} <span className="match-simulation__vs">vs</span> {opponentTeamName}
        </h2>

        {playerDraftWin !== null && (
          <p className="match-simulation__draft-adv">
            Avantage draft : {formatPercent(playerDraftWin)} pour {playerTeamName}
          </p>
        )}

        {loading && <p className="match-simulation__status">Génération du scénario de game…</p>}
        {error && <p className="worlds-error">{error}</p>}

        {result && (
          <>
            <div
              className={`match-simulation__scoreboard ${
                result.player_wins
                  ? "match-simulation__scoreboard--win"
                  : "match-simulation__scoreboard--loss"
              }`}
            >
              <span>{playerTeamName}</span>
              <strong>{result.player_wins ? "VICTOIRE" : "DÉFAITE"}</strong>
              <span>{formatPercent(result.player_win_probability)} pré-match</span>
            </div>

            <ol className="match-simulation__timeline">
              {result.events.slice(0, visibleEvents).map((event, index) => (
                <li
                  key={`${event.minute}-${index}`}
                  className={[
                    "match-simulation__event",
                    `match-simulation__event--${event.side}`,
                    `match-simulation__event--${event.phase}`,
                    index === visibleEvents - 1 ? "match-simulation__event--latest" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <span className="match-simulation__minute">{event.minute}:00</span>
                  <div>
                    <em className="match-simulation__phase">{PHASE_LABELS[event.phase]}</em>
                    <p>{event.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </div>
  );
}
