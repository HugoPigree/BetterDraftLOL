import { useEffect, useRef, useState } from "react";
import { DRAFT_SEQUENCE } from "../draft/sequence";
import type { DraftContext, Team } from "../types/draft";
import type { BotLastMove } from "./useDraftBot";
import {
  botSideForPlayer,
  lineForBotEvent,
  type BotDialogueEvent,
} from "../utils/botDialogue";

interface UseBotDialogueOptions {
  enabled: boolean;
  draft: DraftContext;
  playerSide: Team;
  botThinking: boolean;
  botError: string | null;
  lastBotMove: BotLastMove | null;
}

function lastChampionFromDraft(
  draft: DraftContext,
  team: Team,
  actionType: "ban" | "pick",
): { champion: string } | null {
  if (actionType === "ban") {
    const bans = team === "blue" ? draft.blueBans : draft.redBans;
    const champion = bans[bans.length - 1];
    return champion ? { champion } : null;
  }

  const picks = team === "blue" ? draft.bluePicks : draft.redPicks;
  const last = picks[picks.length - 1];
  return last ? { champion: last.champion } : null;
}

export function useBotDialogue({
  enabled,
  draft,
  playerSide,
  botThinking,
  botError,
  lastBotMove,
}: UseBotDialogueOptions) {
  const [line, setLine] = useState("");
  const prevActionIndexRef = useRef(0);
  const introShownRef = useRef(false);
  const prevThinkingRef = useRef(false);
  const prevErrorRef = useRef<string | null>(null);
  const prevLastMoveRef = useRef<BotLastMove | null>(null);
  const prevPlayerTurnRef = useRef<boolean | null>(null);

  const speak = (event: BotDialogueEvent) => {
    setLine(lineForBotEvent(event));
  };

  useEffect(() => {
    if (!enabled) {
      setLine("");
      introShownRef.current = false;
      prevActionIndexRef.current = 0;
      return;
    }

    if (draft.actionIndex === 0 && prevActionIndexRef.current > 0) {
      introShownRef.current = false;
      prevLastMoveRef.current = null;
    }

    if (!introShownRef.current && draft.actionIndex === 0 && !draft.isDraftComplete) {
      introShownRef.current = true;
      speak({ type: "intro" });
    }
  }, [enabled, draft.actionIndex, draft.isDraftComplete]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    if (botThinking && !prevThinkingRef.current) {
      const action = draft.currentActionType ?? "pick";
      speak({ type: "thinking", action });
    }
    prevThinkingRef.current = botThinking;
  }, [enabled, botThinking, draft.currentActionType]);

  useEffect(() => {
    if (!enabled || !lastBotMove) {
      return;
    }

    if (prevLastMoveRef.current === lastBotMove) {
      return;
    }
    prevLastMoveRef.current = lastBotMove;

    if (lastBotMove.action === "ban") {
      speak({
        type: "bot_ban",
        champion: lastBotMove.champion,
        reason: lastBotMove.reason,
      });
      return;
    }

    speak({
      type: "bot_pick",
      champion: lastBotMove.champion,
      reason: lastBotMove.reason,
    });
  }, [enabled, lastBotMove]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    if (botError && botError !== prevErrorRef.current) {
      speak({ type: "error" });
    }
    prevErrorRef.current = botError;
  }, [enabled, botError]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const prevIndex = prevActionIndexRef.current;
    if (draft.actionIndex <= prevIndex) {
      if (draft.actionIndex === 0) {
        prevActionIndexRef.current = 0;
      }
      return;
    }

    for (let index = prevIndex; index < draft.actionIndex; index += 1) {
      const step = DRAFT_SEQUENCE[index];
      if (!step) {
        continue;
      }

      const payload = lastChampionFromDraft(draft, step.team, step.actionType);
      if (!payload) {
        continue;
      }

      const isPlayer = step.team === playerSide;
      if (isPlayer) {
        if (step.actionType === "ban") {
          speak({ type: "player_ban", champion: payload.champion });
        } else {
          speak({ type: "player_pick", champion: payload.champion });
        }
      }
    }

    prevActionIndexRef.current = draft.actionIndex;

    if (draft.isDraftComplete) {
      speak({ type: "draft_complete" });
    }
  }, [enabled, draft.actionIndex, draft.isDraftComplete, draft.blueBans, draft.redBans, draft.bluePicks, draft.redPicks, playerSide]);

  useEffect(() => {
    if (!enabled || draft.isDraftComplete) {
      return;
    }

    const isPlayerTurn = draft.whoseTurn === playerSide;
    if (prevPlayerTurnRef.current === false && isPlayerTurn && !botThinking) {
      speak({ type: "player_turn" });
    }
    prevPlayerTurnRef.current = isPlayerTurn;
  }, [enabled, draft.whoseTurn, draft.isDraftComplete, playerSide, botThinking]);

  useEffect(() => {
    if (!enabled) {
      prevPlayerTurnRef.current = null;
      prevLastMoveRef.current = null;
      prevThinkingRef.current = false;
      prevErrorRef.current = null;
    }
  }, [enabled]);

  const botSide = botSideForPlayer(playerSide);

  return { line, botSide, visible: enabled && Boolean(line) };
}
