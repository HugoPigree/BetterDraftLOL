import { useEffect, useRef, useState } from "react";
import type { DraftContext, Team } from "../types/draft";
import type { PredictionMode } from "../types/predict";
import { draftBotMove } from "../services/api";
import {
  getAvailableChampions,
  opponentTeam,
  teamPicksForSide,
} from "../utils/draftTeamBuilder";

export interface BotLastMove {
  action: "ban" | "pick";
  champion: string;
}

interface UseDraftBotOptions {
  enabled: boolean;
  draft: DraftContext;
  playerSide: Team;
  champions: string[];
  patch: string;
}

const BOT_MODE: PredictionMode = "pro";

const BOT_DELAY_MS = 600;

export function useDraftBot({
  enabled,
  draft,
  playerSide,
  champions,
  patch,
}: UseDraftBotOptions) {
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastMove, setLastMove] = useState<BotLastMove | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (!enabled || draft.isDraftComplete || champions.length === 0) {
      setThinking(false);
      return;
    }

    const botSide = draft.whoseTurn;
    if (!botSide || botSide === playerSide || !draft.currentActionType) {
      setThinking(false);
      return;
    }

    const side = botSide;
    const actionIndex = draft.actionIndex;
    const actionType = draft.currentActionType;
    const requestId = ++requestIdRef.current;
    let cancelled = false;

    async function playBotTurn() {
      setThinking(true);
      setError(null);

      await new Promise((resolve) => window.setTimeout(resolve, BOT_DELAY_MS));
      if (cancelled || requestId !== requestIdRef.current) {
        return;
      }

      const availableChampions = getAvailableChampions(champions, draft.usedChampions);
      const botPicks = teamPicksForSide(draft, side);
      const opponentPicks = teamPicksForSide(draft, opponentTeam(side));

      try {
        const move = await draftBotMove(
          actionType,
          side,
          botPicks,
          opponentPicks,
          patch,
          availableChampions,
          BOT_MODE,
        );

        if (cancelled || requestId !== requestIdRef.current) {
          return;
        }

        if (draft.actionIndex !== actionIndex) {
          return;
        }

        if (move.action === "pick") {
          draft.selectChampion(move.champion);
          setLastMove({
            action: "pick",
            champion: move.champion,
          });
        } else {
          draft.selectChampion(move.champion);
          setLastMove({ action: "ban", champion: move.champion });
        }
      } catch (botError) {
        if (cancelled || requestId !== requestIdRef.current) {
          return;
        }
        setError(
          botError instanceof Error
            ? botError.message
            : "Le bot n'a pas pu jouer son tour",
        );
      } finally {
        if (!cancelled && requestId === requestIdRef.current) {
          setThinking(false);
        }
      }
    }

    void playBotTurn();

    return () => {
      cancelled = true;
    };
  }, [
    enabled,
    draft.actionIndex,
    draft.whoseTurn,
    draft.currentActionType,
    draft.isDraftComplete,
    draft.usedChampions,
    draft.bluePicks,
    draft.redPicks,
    draft.selectChampion,
    playerSide,
    champions,
    patch,
  ]);

  return { thinking, error, lastMove };
}
