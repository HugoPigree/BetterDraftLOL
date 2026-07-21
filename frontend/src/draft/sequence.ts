import type { Phase, SequenceStep } from "../types/draft";

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

export function getPhaseForIndex(actionIndex: number): Phase {
  if (actionIndex >= DRAFT_SEQUENCE.length) {
    return "complete";
  }
  return DRAFT_SEQUENCE[actionIndex].phase;
}
