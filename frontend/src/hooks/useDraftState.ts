import { useCallback, useMemo, useReducer, useRef } from "react";
import { DRAFT_SEQUENCE, getPhaseForIndex } from "../draft/sequence";
import type {
  DraftContext,
  DraftReducerAction,
  DraftState,
  Role,
  SequenceStep,
} from "../types/draft";

export const ROLES: Role[] = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];

const initialState: DraftState = {
  actionIndex: 0,
  blueBans: [],
  redBans: [],
  bluePicks: [],
  redPicks: [],
  usedChampions: [],
};

function createDraftReducer(getSequence: () => SequenceStep[]) {
  return function draftReducer(state: DraftState, action: DraftReducerAction): DraftState {
    switch (action.type) {
      case "RESET":
        return initialState;

      case "SELECT_CHAMPION": {
        const sequence = getSequence();
        const currentStep = sequence[state.actionIndex];
        if (!currentStep) {
          return state;
        }

        const champion = action.champion.trim();
        if (!champion) {
          return state;
        }

        if (state.usedChampions.includes(champion)) {
          return state;
        }

        const usedChampions = [...state.usedChampions, champion];

        if (currentStep.actionType === "ban") {
          const blueBans =
            currentStep.team === "blue"
              ? [...state.blueBans, champion]
              : state.blueBans;
          const redBans =
            currentStep.team === "red"
              ? [...state.redBans, champion]
              : state.redBans;

          return {
            ...state,
            actionIndex: state.actionIndex + 1,
            blueBans,
            redBans,
            usedChampions,
          };
        }

        const pick = action.role ? { champion, role: action.role } : { champion };
        const bluePicks =
          currentStep.team === "blue"
            ? [...state.bluePicks, pick]
            : state.bluePicks;
        const redPicks =
          currentStep.team === "red" ? [...state.redPicks, pick] : state.redPicks;

        return {
          ...state,
          actionIndex: state.actionIndex + 1,
          bluePicks,
          redPicks,
          usedChampions,
        };
      }

      default:
        return state;
    }
  };
}

export function useDraftState(sequence: SequenceStep[] = DRAFT_SEQUENCE): DraftContext {
  const sequenceRef = useRef(sequence);
  sequenceRef.current = sequence;

  const getSequence = useCallback(() => sequenceRef.current, []);
  const reducer = useMemo(() => createDraftReducer(getSequence), [getSequence]);
  const [state, dispatch] = useReducer(reducer, initialState);

  const currentStep = sequence[state.actionIndex] ?? null;
  const isDraftComplete = state.actionIndex >= sequence.length;
  const currentPhase = getPhaseForIndex(state.actionIndex, sequence);

  const selectChampion = useCallback((champion: string, role?: Role) => {
    dispatch({ type: "SELECT_CHAMPION", champion, role });
  }, []);

  const resetDraft = useCallback(() => {
    dispatch({ type: "RESET" });
  }, []);

  return useMemo(
    () => ({
      state,
      whoseTurn: isDraftComplete ? null : currentStep?.team ?? null,
      currentActionType: isDraftComplete ? null : currentStep?.actionType ?? null,
      currentPhase,
      isDraftComplete,
      actionIndex: state.actionIndex,
      totalActions: sequence.length,
      blueBans: state.blueBans,
      redBans: state.redBans,
      bluePicks: state.bluePicks,
      redPicks: state.redPicks,
      usedChampions: state.usedChampions,
      selectChampion,
      resetDraft,
      sequence,
    }),
    [state, currentStep, isDraftComplete, currentPhase, sequence, selectChampion, resetDraft],
  );
}
