import { useEffect, useRef, useState } from "react";
import type { DraftContext } from "../types/draft";
import type { WorldsTeam } from "../types/worlds";
import type { BotLastMove } from "./useTeamDraftBot";
import { coachLineForTeam } from "../utils/worldsCoachDialogue";

interface UseWorldsCoachDialogueOptions {
  enabled: boolean;
  opponent: WorldsTeam | null;
  draft: DraftContext;
  playerSide: "blue" | "red";
  botThinking: boolean;
  botError: string | null;
  lastBotMove: BotLastMove | null;
}

export function useWorldsCoachDialogue({
  enabled,
  opponent,
  draft,
  playerSide,
  botThinking,
  botError,
  lastBotMove,
}: UseWorldsCoachDialogueOptions) {
  const [line, setLine] = useState("");
  const introShownRef = useRef(false);
  const prevThinkingRef = useRef(false);
  const prevErrorRef = useRef<string | null>(null);
  const prevLastMoveRef = useRef<BotLastMove | null>(null);

  const isPlayerTurn =
    !draft.isDraftComplete &&
    draft.whoseTurn === playerSide &&
    !botThinking;

  const isBotMoment = botThinking || draft.whoseTurn !== playerSide;

  useEffect(() => {
    if (!enabled || !opponent) {
      setLine("");
      introShownRef.current = false;
      return;
    }
    if (isPlayerTurn) {
      setLine("");
      return;
    }
    if (!introShownRef.current && isBotMoment && draft.actionIndex === 0) {
      introShownRef.current = true;
      setLine(coachLineForTeam(opponent, { type: "intro" }));
    }
  }, [enabled, opponent, draft.actionIndex, isBotMoment, isPlayerTurn]);

  useEffect(() => {
    if (!enabled || !opponent || isPlayerTurn) {
      return;
    }
    if (botThinking && !prevThinkingRef.current) {
      setLine(coachLineForTeam(opponent, { type: "thinking" }));
    }
    prevThinkingRef.current = botThinking;
  }, [enabled, opponent, botThinking, isPlayerTurn]);

  useEffect(() => {
    if (!enabled || !opponent || !lastBotMove || isPlayerTurn) {
      return;
    }
    if (prevLastMoveRef.current === lastBotMove) {
      return;
    }
    prevLastMoveRef.current = lastBotMove;
    if (lastBotMove.action === "ban") {
      setLine(coachLineForTeam(opponent, { type: "ban", champion: lastBotMove.champion }));
    } else {
      setLine(coachLineForTeam(opponent, { type: "pick", champion: lastBotMove.champion }));
    }
  }, [enabled, opponent, lastBotMove, isPlayerTurn]);

  useEffect(() => {
    if (!enabled || !opponent || isPlayerTurn) {
      return;
    }
    if (botError && botError !== prevErrorRef.current) {
      setLine(coachLineForTeam(opponent, { type: "error", detail: botError }));
    }
    prevErrorRef.current = botError;
  }, [enabled, opponent, botError, isPlayerTurn]);

  const botSide: "blue" | "red" = playerSide === "blue" ? "red" : "blue";

  return {
    line,
    botSide,
    visible: enabled && Boolean(line) && Boolean(opponent) && !isPlayerTurn,
  };
}
