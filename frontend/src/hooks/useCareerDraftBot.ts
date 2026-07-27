import { useEffect, useRef, useState } from "react";
import type { DraftContext, Team } from "../types/draft";
import type { LecCareerPatch, LecPlayerProfile, LecTeamIdentity } from "../types/lec";
import { lecCareerDraftBotMove } from "../services/api";
import {
  getAvailableChampions,
  opponentTeam,
  teamPicksForSide,
} from "../utils/draftTeamBuilder";
import type { BotLastMove } from "./useTeamDraftBot";

export type { BotLastMove };

interface UseCareerDraftBotOptions {
  enabled: boolean;
  draft: DraftContext;
  playerSide: Team;
  champions: string[];
  careerPatch: LecCareerPatch;
  teamIdentity: LecTeamIdentity;
  teamProfiles: LecPlayerProfile[];
  opponentProfiles?: LecPlayerProfile[];
  draftSeed?: string;
}

const BOT_DELAY_MS = 0;

export function useCareerDraftBot({
  enabled,
  draft,
  playerSide,
  champions,
  careerPatch,
  teamIdentity,
  teamProfiles,
  opponentProfiles = [],
  draftSeed = "",
}: UseCareerDraftBotOptions) {
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
        const moveSeed = hashDraftSeed(
          draftSeed,
          teamIdentity.team_id,
          actionIndex,
          actionType,
          careerPatch.patch_id,
        );
        const move = await lecCareerDraftBotMove(
          actionType,
          side,
          botPicks,
          opponentPicks,
          availableChampions,
          teamIdentity,
          teamProfiles,
          careerPatch,
          moveSeed,
          opponentProfiles,
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
    careerPatch,
    teamIdentity,
    teamProfiles,
    opponentProfiles,
    draftSeed,
  ]);

  return { thinking, error, lastMove };
}

function hashDraftSeed(
  draftSeed: string,
  teamId: string,
  actionIndex: number,
  actionType: "ban" | "pick",
  patchId: string,
): number {
  const raw = `${draftSeed}|${teamId}|${actionIndex}|${actionType}|${patchId}`;
  let hash = 2166136261;
  for (let index = 0; index < raw.length; index += 1) {
    hash ^= raw.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}
