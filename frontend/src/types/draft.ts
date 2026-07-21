export type Team = "blue" | "red";
export type ActionType = "ban" | "pick";
export type Phase = "ban1" | "pick1" | "ban2" | "pick2" | "complete";
export type Role = "TOP" | "JUNGLE" | "MIDDLE" | "BOTTOM" | "UTILITY";

export interface DraftPick {
  champion: string;
  role: Role;
}

export interface SequenceStep {
  team: Team;
  actionType: ActionType;
  phase: Phase;
}

export interface DraftState {
  actionIndex: number;
  blueBans: string[];
  redBans: string[];
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  usedChampions: string[];
}

export interface DraftContext {
  state: DraftState;
  whoseTurn: Team | null;
  currentActionType: ActionType | null;
  currentPhase: Phase;
  isDraftComplete: boolean;
  actionIndex: number;
  totalActions: number;
  blueBans: string[];
  redBans: string[];
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  usedChampions: string[];
  selectChampion: (champion: string, role?: Role) => void;
  resetDraft: () => void;
}

export type DraftReducerAction =
  | { type: "SELECT_CHAMPION"; champion: string; role?: Role }
  | { type: "RESET" };
