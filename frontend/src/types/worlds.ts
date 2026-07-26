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
  minute: number;
  phase: "early" | "mid" | "late";
  side: "blue" | "red";
  text: string;
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
