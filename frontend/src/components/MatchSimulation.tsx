import { useCallback, useEffect, useRef, useState } from "react";
import type { MatchSimulationEvent, MatchSimulationResult } from "../types/worlds";
import type { PredictResponse } from "../types/predict";
import type { Team } from "../types/draft";
import type { WorldsRoster } from "../types/worlds";
import {
  resolveWorldsSimulationPhase,
  startWorldsSimulation,
} from "../services/api";

interface MatchSimulationProps {
  playerTeamName: string;
  opponentTeamName: string;
  opponentTeamId?: string;
  playerRoster?: WorldsRoster;
  opponentRoster?: WorldsRoster;
  playerSide: Team;
  draftPrediction: PredictResponse;
  onComplete: (playerWins: boolean, result: MatchSimulationResult) => void;
}

type SimMode =
  | "booting"
  | "early_decision"
  | "early_feedback"
  | "mid_decision"
  | "mid_feedback"
  | "replaying"
  | "done";

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

const PHASE_LABELS: Record<string, string> = {
  early: "Early game",
  mid: "Mid game",
  late: "Late game",
};

const REVEAL_MS = 1100;
const FEEDBACK_MS = 2200;

function resolveResponseToResult(response: {
  player_wins?: boolean;
  player_win_probability?: number;
  draft_blue_win_probability?: number;
  winner_side?: "blue" | "red";
  winner_team_name?: string;
  loser_team_name?: string;
  blue_win_probability?: number;
  events?: MatchSimulationEvent[];
  game_length_minutes?: number;
  phases_won?: number;
}): MatchSimulationResult | null {
  if (
    response.player_wins === undefined ||
    !response.winner_side ||
    !response.winner_team_name ||
    !response.loser_team_name ||
    !response.events
  ) {
    return null;
  }
  return {
    player_wins: response.player_wins,
    player_win_probability: response.player_win_probability ?? 0.5,
    draft_blue_win_probability: response.draft_blue_win_probability ?? 0.5,
    winner_side: response.winner_side,
    winner_team_name: response.winner_team_name,
    loser_team_name: response.loser_team_name,
    blue_win_probability: response.blue_win_probability ?? 0.5,
    events: response.events,
    game_length_minutes: response.game_length_minutes ?? 38,
    phases_won: response.phases_won,
  };
}

export function MatchSimulation({
  playerTeamName,
  opponentTeamName,
  opponentTeamId,
  playerRoster,
  opponentRoster,
  playerSide,
  draftPrediction,
  onComplete,
}: MatchSimulationProps) {
  const [mode, setMode] = useState<SimMode>("booting");
  const [error, setError] = useState<string | null>(null);
  const [simulationToken, setSimulationToken] = useState<string | null>(null);
  const [earlyContext, setEarlyContext] = useState("");
  const [midContext, setMidContext] = useState("");
  const [feedbackText, setFeedbackText] = useState("");
  const [phaseWon, setPhaseWon] = useState<boolean | null>(null);
  const [result, setResult] = useState<MatchSimulationResult | null>(null);
  const [visibleEvents, setVisibleEvents] = useState(0);
  const [resolving, setResolving] = useState(false);
  const bootedRef = useRef(false);

  const playerDraftWin =
    playerSide === "blue"
      ? draftPrediction.blue_win_probability
      : draftPrediction.red_win_probability;

  useEffect(() => {
    if (bootedRef.current) {
      return;
    }
    bootedRef.current = true;
    void (async () => {
      try {
        const started = await startWorldsSimulation(
          playerSide,
          playerTeamName,
          opponentTeamName,
          draftPrediction,
          opponentTeamId,
          playerRoster,
          opponentRoster,
        );
        setSimulationToken(started.simulation_token);
        setEarlyContext(started.early_context);
        setMode("early_decision");
      } catch (bootError) {
        setError(
          bootError instanceof Error ? bootError.message : "Simulation impossible",
        );
      }
    })();
  }, [
    draftPrediction,
    opponentRoster,
    opponentTeamId,
    opponentTeamName,
    playerRoster,
    playerSide,
    playerTeamName,
  ]);

  const handleChoice = useCallback(
    async (phase: "early" | "mid", choice: "engage" | "temporize") => {
      if (!simulationToken || resolving) {
        return;
      }
      setResolving(true);
      setError(null);
      try {
        const response = await resolveWorldsSimulationPhase(simulationToken, phase, choice);
        if (response.simulation_token) {
          setSimulationToken(response.simulation_token);
        }
        setPhaseWon(response.phase_won);
        setFeedbackText(response.explanation_text);

        if (response.status === "awaiting_decision") {
          setMidContext(response.mid_context ?? "");
          setMode("early_feedback");
          return;
        }

        const finalResult = resolveResponseToResult(response);
        if (!finalResult) {
          throw new Error("Réponse de simulation incomplète.");
        }
        setResult(finalResult);
        setMode("mid_feedback");
      } catch (resolveError) {
        setError(
          resolveError instanceof Error ? resolveError.message : "Phase impossible",
        );
      } finally {
        setResolving(false);
      }
    },
    [resolving, simulationToken],
  );

  useEffect(() => {
    if (mode !== "early_feedback") {
      return;
    }
    const timer = window.setTimeout(() => setMode("mid_decision"), FEEDBACK_MS);
    return () => window.clearTimeout(timer);
  }, [mode]);

  useEffect(() => {
    if (mode !== "mid_feedback" || !result) {
      return;
    }
    const timer = window.setTimeout(() => {
      setVisibleEvents(0);
      setMode("replaying");
    }, FEEDBACK_MS);
    return () => window.clearTimeout(timer);
  }, [mode, result]);

  useEffect(() => {
    if (mode !== "replaying" || !result) {
      return;
    }
    setVisibleEvents(0);
    const timers: number[] = [];
    result.events.forEach((_event, index) => {
      timers.push(
        window.setTimeout(() => {
          setVisibleEvents(index + 1);
        }, (index + 1) * REVEAL_MS),
      );
    });
    timers.push(
      window.setTimeout(() => {
        setMode("done");
      }, result.events.length * REVEAL_MS + 800),
    );
    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [mode, result]);

  useEffect(() => {
    if (mode === "done" && result) {
      const timer = window.setTimeout(() => onComplete(result.player_wins, result), 1400);
      return () => window.clearTimeout(timer);
    }
  }, [mode, onComplete, result]);

  function renderDecisionPanel(context: string, phase: "early" | "mid") {
    return (
      <div className="match-simulation__decision">
        <p className="match-simulation__decision-context">{context}</p>
        <div className="match-simulation__decision-actions">
          <button
            type="button"
            className="worlds-btn worlds-btn--primary"
            disabled={resolving}
            onClick={() => void handleChoice(phase, "engage")}
          >
            Engager
          </button>
          <button
            type="button"
            className="worlds-btn worlds-btn--ghost"
            disabled={resolving}
            onClick={() => void handleChoice(phase, "temporize")}
          >
            Temporiser
          </button>
        </div>
      </div>
    );
  }

  function renderFeedback() {
    if (!feedbackText) {
      return null;
    }
    return (
      <div
        className={`match-simulation__phase-result ${
          phaseWon ? "match-simulation__phase-result--win" : "match-simulation__phase-result--loss"
        }`}
      >
        <strong>{phaseWon ? "Phase remportée" : "Phase perdue"}</strong>
        <p>{feedbackText}</p>
      </div>
    );
  }

  function renderEvent(event: MatchSimulationEvent, index: number) {
    if (event.type === "decision") {
      return (
        <li
          key={`decision-${event.phase}-${index}`}
          className={[
            "match-simulation__event",
            "match-simulation__event--decision",
            index === visibleEvents - 1 ? "match-simulation__event--latest" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <span className="match-simulation__minute">{event.minute}:00</span>
          <div>
            <em className="match-simulation__phase">{PHASE_LABELS[event.phase] ?? event.phase}</em>
            <p className="match-simulation__decision-choice">
              Décision : {event.player_choice === "engage" ? "Engager" : "Temporiser"}
              {" · "}
              {event.phase_won ? "Phase gagnée" : "Phase perdue"}
            </p>
            {event.explanation_text && <p>{event.explanation_text}</p>}
          </div>
        </li>
      );
    }

    if (event.type === "phase_result") {
      return (
        <li
          key={`phase-result-${event.phase}-${index}`}
          className={[
            "match-simulation__event",
            "match-simulation__event--phase-result",
            index === visibleEvents - 1 ? "match-simulation__event--latest" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <span className="match-simulation__minute">{event.minute}:00</span>
          <div>
            <em className="match-simulation__phase">{PHASE_LABELS[event.phase] ?? event.phase}</em>
            <p>
              Late game auto — {event.phase_won ? "phase gagnée" : "phase perdue"}
            </p>
            {event.explanation_text && <p>{event.explanation_text}</p>}
          </div>
        </li>
      );
    }

    return (
      <li
        key={`${event.minute}-${index}`}
        className={[
          "match-simulation__event",
          event.side ? `match-simulation__event--${event.side}` : "",
          `match-simulation__event--${event.phase}`,
          index === visibleEvents - 1 ? "match-simulation__event--latest" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <span className="match-simulation__minute">{event.minute}:00</span>
        <div>
          <em className="match-simulation__phase">{PHASE_LABELS[event.phase] ?? event.phase}</em>
          <p>{event.text}</p>
        </div>
      </li>
    );
  }

  const showScoreboard = result && (mode === "replaying" || mode === "done");

  return (
    <div className="worlds-screen worlds-screen--center worlds-simulation">
      <div className="match-simulation">
        <p className="match-simulation__eyebrow">Worlds · Simulation live</p>
        <h2>
          {playerTeamName} <span className="match-simulation__vs">vs</span> {opponentTeamName}
        </h2>

        <p className="match-simulation__draft-adv">
          Avantage draft : {formatPercent(playerDraftWin)} pour {playerTeamName}
        </p>

        {mode === "booting" && (
          <p className="match-simulation__status">Préparation de la simulation…</p>
        )}
        {error && <p className="worlds-error">{error}</p>}

        {mode === "early_decision" && renderDecisionPanel(earlyContext, "early")}
        {mode === "early_feedback" && renderFeedback()}
        {mode === "mid_decision" && renderDecisionPanel(midContext, "mid")}
        {mode === "mid_feedback" && renderFeedback()}

        {showScoreboard && result && (
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
              <span>
                {formatPercent(result.player_win_probability)} pré-match
                {result.phases_won !== undefined ? ` · ${result.phases_won}/3 phases` : ""}
              </span>
            </div>

            <ol className="match-simulation__timeline">
              {result.events.slice(0, visibleEvents).map((event, index) => renderEvent(event, index))}
            </ol>
          </>
        )}
      </div>
    </div>
  );
}
