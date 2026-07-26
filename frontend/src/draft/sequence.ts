import type { DraftPreferences, Phase, SequenceStep } from "../types/draft";

export const DRAFT_SEQUENCE: SequenceStep[] = [
  // Ban phase 1: Blue, Red, Blue, Red, Blue, Red
  { team: "blue", actionType: "ban", phase: "ban1" },
  { team: "red", actionType: "ban", phase: "ban1" },
  { team: "blue", actionType: "ban", phase: "ban1" },
  { team: "red", actionType: "ban", phase: "ban1" },
  { team: "blue", actionType: "ban", phase: "ban1" },
  { team: "red", actionType: "ban", phase: "ban1" },

  // Pick phase 1: Blue, Red, Red, Blue, Blue, Red (1-2-2-1)
  { team: "blue", actionType: "pick", phase: "pick1" },
  { team: "red", actionType: "pick", phase: "pick1" },
  { team: "red", actionType: "pick", phase: "pick1" },
  { team: "blue", actionType: "pick", phase: "pick1" },
  { team: "blue", actionType: "pick", phase: "pick1" },
  { team: "red", actionType: "pick", phase: "pick1" },

  // Ban phase 2: Red, Blue, Red, Blue
  { team: "red", actionType: "ban", phase: "ban2" },
  { team: "blue", actionType: "ban", phase: "ban2" },
  { team: "red", actionType: "ban", phase: "ban2" },
  { team: "blue", actionType: "ban", phase: "ban2" },

  // Pick phase 2: Red, Blue, Blue, Red (1-2-1)
  { team: "red", actionType: "pick", phase: "pick2" },
  { team: "blue", actionType: "pick", phase: "pick2" },
  { team: "blue", actionType: "pick", phase: "pick2" },
  { team: "red", actionType: "pick", phase: "pick2" },
];

export function firstPickIsBlue(preferences: DraftPreferences): boolean {
  return preferences.pickOrder === "first"
    ? preferences.playerSide === "blue"
    : preferences.playerSide === "red";
}

export function buildDraftSequence(preferences: DraftPreferences): SequenceStep[] {
  return buildDraftSequenceForFirstPick(firstPickIsBlue(preferences));
}

export function buildDraftSequenceForFirstPick(firstPickIsBlueSide: boolean): SequenceStep[] {
  if (firstPickIsBlueSide) {
    return DRAFT_SEQUENCE;
  }
  return DRAFT_SEQUENCE.map((step) => ({
    ...step,
    team: step.team === "blue" ? "red" : "blue",
  }));
}

export function getPhaseForIndex(
  actionIndex: number,
  sequence: SequenceStep[] = DRAFT_SEQUENCE,
): Phase {
  if (actionIndex >= sequence.length) {
    return "complete";
  }
  return sequence[actionIndex].phase;
}
