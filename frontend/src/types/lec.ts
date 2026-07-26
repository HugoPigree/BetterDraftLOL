import type { DraftPreferences } from "./draft";
import type { WorldsRoster, WorldsTeam, BracketMatch } from "./worlds";

export type LecPhase =
  | "setup"
  | "storyIntro"
  | "seasonHub"
  | "storyBeat"
  | "matchIntro"
  | "drafting"
  | "draftResult"
  | "simulating"
  | "matchResult"
  | "playoffsHub"
  | "playoffIntro"
  | "seasonEnd"
  | "worldsQualified";

export interface LecTeam extends WorldsTeam {
  short_name?: string;
  brand_color?: string;
  power_rating?: number;
  playoff_seed?: number;
}

export interface LecFixture {
  id: string;
  week: number;
  stage: "regular" | "playoffs";
  format: "bo1" | "bo3" | "bo5";
  round_label: string;
  team_a_id: string;
  team_b_id: string;
  winner_id: string | null;
  is_player_match: boolean;
  played: boolean;
}

export interface LecStandingRow {
  rank: number;
  team_id: string;
  team_name: string;
  short_name: string;
  brand_color: string;
  wins: number;
  losses: number;
  played: number;
  win_rate: number;
  is_player_team: boolean;
  playoffs_cutoff: boolean;
  worlds_cutoff: boolean;
}

export interface LecSeasonState {
  season_label: string;
  format: Record<string, unknown>;
  teams: LecTeam[];
  fixtures: LecFixture[];
  standings: LecStandingRow[];
  current_week: number;
  story_chapter: number;
  playoffs?: BracketMatch[] | null;
  regular_complete?: boolean;
}

export interface LecRecordResultResponse {
  fixtures: LecFixture[];
  standings: LecStandingRow[];
  next_fixture: LecFixture | null;
  regular_complete: boolean;
  playoffs: BracketMatch[] | null;
  player_rank: number | null;
  player_playoffs: boolean;
  player_worlds: boolean;
}

export interface LecStoryLine {
  speaker: string;
  portraitTeamId?: string;
  text: string;
  mood?: "neutral" | "tension" | "triumph" | "doubt";
}

export interface LecStoryChapter {
  id: string;
  title: string;
  trigger: "intro" | "week" | "playoffs" | "worlds" | "eliminated";
  triggerWeek?: number;
  lines: LecStoryLine[];
}

export interface LecCareerSnapshot {
  phase: LecPhase;
  season: LecSeasonState;
  draftPreferences: DraftPreferences;
  currentFixtureId: string | null;
  currentPlayoffMatchId: string | null;
  storyChapterSeen: string[];
  pendingStoryChapterId: string | null;
}

export const LEC_ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"] as const;

export const EMPTY_LEC_ROSTER: WorldsRoster = {
  TOP: "",
  JUNGLE: "",
  MIDDLE: "",
  BOTTOM: "",
  UTILITY: "",
};
