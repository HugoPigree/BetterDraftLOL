import type { Role } from "./draft";

export type WorldsRound = "quarter" | "semi" | "final";

export interface WorldsRoster {
  TOP: string;
  JUNGLE: string;
  MIDDLE: string;
  BOTTOM: string;
  UTILITY: string;
}

export interface WorldsTeam {
  id: string;
  name: string;
  region: string;
  coach: string;
  roster: WorldsRoster;
  is_player_team?: boolean;
  coach_portrait?: string | null;
}

export interface BracketTeamSlot {
  team: WorldsTeam | null;
  source_match_id: string | null;
}

export interface BracketMatch {
  id: string;
  round: WorldsRound;
  round_label: string;
  team_a: BracketTeamSlot;
  team_b: BracketTeamSlot;
  winner_id: string | null;
}

export interface WorldsStartResponse {
  player_team: WorldsTeam;
  opponent_teams: WorldsTeam[];
  bracket: BracketMatch[];
}

export interface MatchSimulationEvent {
  type?: "flavor" | "decision" | "phase_result";
  minute: number;
  phase: "early" | "mid" | "late";
  side?: "blue" | "red";
  text?: string;
  choices?: Array<"engage" | "temporize">;
  context_text?: string;
  resolved?: boolean;
  player_choice?: "engage" | "temporize" | null;
  phase_won?: boolean;
  explanation_text?: string | null;
  phase_probability?: number;
  auto_resolved?: boolean;
}

export interface MatchSimulationStartResponse {
  simulation_id: string;
  status: "awaiting_decision";
  pending_phase: "early" | "mid";
  early_context: string;
  player_win_probability: number;
  draft_blue_win_probability: number;
  phase_advantages: Record<"early" | "mid" | "late", number>;
}

export interface MatchSimulationResolveResponse {
  simulation_id: string;
  status: "awaiting_decision" | "complete";
  pending_phase?: "mid";
  resolved_phase: "early" | "mid" | "late";
  phase_won: boolean;
  phase_probability: number;
  explanation_text: string;
  mid_context?: string;
  player_wins?: boolean;
  player_win_probability?: number;
  draft_blue_win_probability?: number;
  winner_side?: "blue" | "red";
  winner_team_name?: string;
  loser_team_name?: string;
  blue_win_probability?: number;
  events?: MatchSimulationEvent[];
  game_length_minutes?: number;
  phases_won?: number;
}

export interface MatchSimulationResult {
  player_wins: boolean;
  player_win_probability: number;
  draft_blue_win_probability: number;
  winner_side: "blue" | "red";
  winner_team_name: string;
  loser_team_name: string;
  blue_win_probability: number;
  events: MatchSimulationEvent[];
  game_length_minutes: number;
  phases_won?: number;
}

export type WorldsPhase =
  | "setup"
  | "bracket"
  | "matchIntro"
  | "drafting"
  | "draftResult"
  | "simulating"
  | "matchResult"
  | "champion"
  | "eliminated";

export const WORLDS_ROLES: Role[] = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];

export const EMPTY_WORLDS_ROSTER: WorldsRoster = {
  TOP: "",
  JUNGLE: "",
  MIDDLE: "",
  BOTTOM: "",
  UTILITY: "",
};

/** Exemple T1 — tests / démo uniquement. */
export const DEFAULT_WORLDS_ROSTER: WorldsRoster = {
  TOP: "Zeus",
  JUNGLE: "Oner",
  MIDDLE: "Faker",
  BOTTOM: "Gumayusi",
  UTILITY: "Keria",
};
