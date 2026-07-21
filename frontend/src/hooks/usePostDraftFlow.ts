import { useCallback, useEffect, useMemo, useState } from "react";
import type { DraftContext, DraftPick, Team } from "../types/draft";
import {
  autoAssignTeamRoles,
  syncPickRolesBySlotOrder,
  validateTeamRoles,
} from "../utils/autoAssignRoles";

export type PostDraftPhase = "drafting" | "confirmRoles" | "result";

export interface SelectedCompSlot {
  side: Team;
  slotIndex: number;
}

export function usePostDraftFlow(
  draft: DraftContext,
  championPositions: Record<string, import("../types/draft").Role[]>,
) {
  const [phase, setPhase] = useState<PostDraftPhase>("drafting");
  const [bluePicks, setBluePicks] = useState<DraftPick[]>([]);
  const [redPicks, setRedPicks] = useState<DraftPick[]>([]);
  const [blueConfirmed, setBlueConfirmed] = useState(false);
  const [redConfirmed, setRedConfirmed] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<SelectedCompSlot | null>(null);

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
      setIsEditing(false);
      setSelectedSlot(null);
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

  const startEditing = useCallback(() => {
    setIsEditing(true);
    setSelectedSlot(null);
  }, []);

  const stopEditing = useCallback(() => {
    setIsEditing(false);
    setSelectedSlot(null);
  }, []);

  const selectSlot = useCallback((side: Team, slotIndex: number) => {
    setSelectedSlot({ side, slotIndex });
  }, []);

  const clearSelectedSlot = useCallback(() => {
    setSelectedSlot(null);
  }, []);

  const replacePick = useCallback(
    (side: Team, slotIndex: number, newChampion: string) => {
      const picks = side === "blue" ? bluePicks : redPicks;
      const otherPicks = side === "blue" ? redPicks : bluePicks;
      const banned = new Set([...draft.blueBans, ...draft.redBans]);
      const usedElsewhere = new Set([
        ...otherPicks.map((pick) => pick.champion),
        ...picks.filter((_, index) => index !== slotIndex).map((pick) => pick.champion),
      ]);

      if (banned.has(newChampion) || usedElsewhere.has(newChampion)) {
        return;
      }

      const updated = picks.map((pick, index) =>
        index === slotIndex ? { ...pick, champion: newChampion } : pick,
      );

      if (side === "blue") {
        updateBluePicks(updated);
      } else {
        updateRedPicks(updated);
      }
    },
    [bluePicks, redPicks, draft.blueBans, draft.redBans, updateBluePicks, updateRedPicks],
  );

  const replaceSelectedPick = useCallback(
    (champion: string) => {
      if (!selectedSlot) {
        return;
      }
      replacePick(selectedSlot.side, selectedSlot.slotIndex, champion);
      setSelectedSlot(null);
    },
    [selectedSlot, replacePick],
  );

  const resetFlow = useCallback(() => {
    setPhase("drafting");
    setBlueConfirmed(false);
    setRedConfirmed(false);
    setBluePicks([]);
    setRedPicks([]);
    setIsEditing(false);
    setSelectedSlot(null);
  }, []);

  const confirmedDraft = useMemo(
    (): DraftContext => ({
      ...draft,
      bluePicks,
      redPicks,
    }),
    [draft, bluePicks, redPicks],
  );

  const usedChampionsForAnalysis = useMemo(
    () => [
      ...draft.blueBans,
      ...draft.redBans,
      ...bluePicks.map((pick) => pick.champion),
      ...redPicks.map((pick) => pick.champion),
    ],
    [draft.blueBans, draft.redBans, bluePicks, redPicks],
  );

  return {
    phase,
    bluePicks,
    redPicks,
    blueConfirmed,
    redConfirmed,
    blueValidation,
    redValidation,
    isEditing,
    selectedSlot,
    updateBluePicks,
    updateRedPicks,
    confirmTeam,
    startEditing,
    stopEditing,
    selectSlot,
    clearSelectedSlot,
    replacePick,
    replaceSelectedPick,
    resetFlow,
    confirmedDraft,
    usedChampionsForAnalysis,
  };
}
