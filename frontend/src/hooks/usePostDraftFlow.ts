import { useCallback, useEffect, useMemo, useState } from "react";
import type { DraftContext, DraftPick, Team } from "../types/draft";
import {
  autoAssignTeamRoles,
  syncPickRolesBySlotOrder,
  validateTeamRoles,
} from "../utils/autoAssignRoles";

export type PostDraftPhase = "drafting" | "confirmRoles" | "result";

export function usePostDraftFlow(
  draft: DraftContext,
  championPositions: Record<string, import("../types/draft").Role[]>,
) {
  const [phase, setPhase] = useState<PostDraftPhase>("drafting");
  const [bluePicks, setBluePicks] = useState<DraftPick[]>([]);
  const [redPicks, setRedPicks] = useState<DraftPick[]>([]);
  const [blueConfirmed, setBlueConfirmed] = useState(false);
  const [redConfirmed, setRedConfirmed] = useState(false);

  useEffect(() => {
    if (!draft.isDraftComplete) {
      return;
    }
    if (Object.keys(championPositions).length === 0) {
      return;
    }
    if (blueConfirmed || redConfirmed) {
      return;
    }

    const blueChampions = draft.bluePicks.map((pick) => pick.champion);
    const redChampions = draft.redPicks.map((pick) => pick.champion);

    setBluePicks(autoAssignTeamRoles(blueChampions, championPositions));
    setRedPicks(autoAssignTeamRoles(redChampions, championPositions));

    if (phase === "drafting") {
      setPhase("confirmRoles");
    }
  }, [
    draft.isDraftComplete,
    draft.bluePicks,
    draft.redPicks,
    championPositions,
    phase,
    blueConfirmed,
    redConfirmed,
  ]);

  useEffect(() => {
    if (!draft.isDraftComplete && phase !== "drafting") {
      setPhase("drafting");
      setBlueConfirmed(false);
      setRedConfirmed(false);
      setBluePicks([]);
      setRedPicks([]);
    }
  }, [draft.isDraftComplete, phase]);

  const blueValidation = useMemo(() => validateTeamRoles(bluePicks), [bluePicks]);
  const redValidation = useMemo(() => validateTeamRoles(redPicks), [redPicks]);

  const updateBluePicks = useCallback((picks: DraftPick[]) => {
    setBluePicks(syncPickRolesBySlotOrder(picks));
    setBlueConfirmed(false);
  }, []);

  const updateRedPicks = useCallback((picks: DraftPick[]) => {
    setRedPicks(syncPickRolesBySlotOrder(picks));
    setRedConfirmed(false);
  }, []);

  const confirmTeam = useCallback(
    (side: Team) => {
      const validation = side === "blue" ? blueValidation : redValidation;
      if (!validation.valid) {
        return;
      }
      if (side === "blue") {
        setBlueConfirmed(true);
      } else {
        setRedConfirmed(true);
      }
    },
    [blueValidation, redValidation],
  );

  useEffect(() => {
    if (phase === "confirmRoles" && blueConfirmed && redConfirmed) {
      setPhase("result");
    }
  }, [phase, blueConfirmed, redConfirmed]);

  const resetFlow = useCallback(() => {
    setPhase("drafting");
    setBlueConfirmed(false);
    setRedConfirmed(false);
    setBluePicks([]);
    setRedPicks([]);
  }, []);

  const confirmedDraft = useMemo(
    (): DraftContext => ({
      ...draft,
      bluePicks,
      redPicks,
    }),
    [draft, bluePicks, redPicks],
  );

  return {
    phase,
    bluePicks,
    redPicks,
    blueConfirmed,
    redConfirmed,
    blueValidation,
    redValidation,
    updateBluePicks,
    updateRedPicks,
    confirmTeam,
    resetFlow,
    confirmedDraft,
  };
}
