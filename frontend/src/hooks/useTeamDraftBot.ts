import { useEffect, useRef, useState } from "react";
import type { DraftContext, Team } from "../types/draft";
import type { WorldsRoster } from "../types/worlds";
import { worldsDraftBotMove } from "../services/api";
import {
  getAvailableChampions,
  opponentTeam,
  teamPicksForSide,
} from "../utils/draftTeamBuilder";

export interface BotLastMove {
  action: "ban" | "pick";
  champion: string;
  reason?: string | null;
}

interface UseTeamDraftBotOptions {
  enabled: boolean;
  draft: DraftContext;
  playerSide: Team;
  champions: string[];
  patch: string;
  opponentTeamId: string;
  opponentRoster: WorldsRoster;
}

const BOT_DELAY_MS = 0;

export function useTeamDraftBot({
  enabled,
  draft,
  playerSide,
  champions,
  patch,
  opponentTeamId,
  opponentRoster,
}: UseTeamDraftBotOptions) {
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
        const move = await worldsDraftBotMove(
          actionType,
          side,
          botPicks,
          opponentPicks,
          patch,
          availableChampions,
          opponentTeamId,
          opponentRoster,
        );

        if (cancelled || requestId !== requestIdRef.current) {
          return;
        }
        if (draft.actionIndex !== actionIndex) {
          return;
        }

        draft.selectChampion(move.champion, move.role ?? undefined);
        setLastMove({
          action: move.action,
          champion: move.champion,
          reason: move.reason,
        });
      } catch (botError) {
        if (cancelled || requestId !== requestIdRef.current) {
          return;
        }
        setError(
          botError instanceof Error
            ? botError.message
            : "Le bot adversaire n'a pas pu jouer",
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
    opponentTeamId,
    opponentRoster,
  ]);

  return { thinking, error, lastMove };
}
