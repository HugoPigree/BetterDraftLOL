import type { DraftPick, Role } from "./draft";

export type PredictionMode = "mixed" | "pro";

export interface ChampionForceDetail {
  champion: string;
  role: Role;
  winrate: number | null;
  games?: number | null;
  insufficient_data?: boolean;
  data_source?: "soloq" | "pro" | null;
}

export interface AttributeProfile {
  damage_mean: number;
  toughness_mean: number;
  control_mean: number;
  mobility_mean: number;
  utility_mean: number;
}

export interface MerakiRoleCount {
  role: string;
  count: number;
}

export interface SynergyContribution {
  champion: string;
  role: Role;
  marginal_points: number;
}

export interface TeamSynergyInsight {
  contributions: SynergyContribution[];
  top_contributor: SynergyContribution;
  least_contributor: SynergyContribution;
  explanation?: string;
}

export interface DuoSynergyDetail {
  champions: string[];
  score: number | null;
  games: number;
  is_fallback: boolean;
  insufficient_data?: boolean;
}

export interface TeamDuoSynergies {
  duo_jungle_support: DuoSynergyDetail;
  duo_bot_lane: DuoSynergyDetail;
}

export interface SideDuoSynergies {
  blue: TeamDuoSynergies;
  red: TeamDuoSynergies;
}

export interface DuoAdvantage {
  stronger_side: "blue" | "red" | "even";
  difference: number;
  insufficient_data?: boolean;
  comparison_message?: string | null;
  insufficient_sides?: Array<"blue" | "red">;
}

export interface DuoDifferential {
  jungle_support_advantage: DuoAdvantage;
  bot_lane_advantage: DuoAdvantage;
}

export interface BotLaneMatchupDetail {
  blue_champions: string[];
  red_champions: string[];
  blue_win_probability: number | null;
  games: number;
  is_fallback: boolean;
  method: "measured" | "blended" | "soloq_composite";
  insufficient_data?: boolean;
}

export type DuoMatchupDetail = BotLaneMatchupDetail;

export interface TeamPredictionDetail {
  score_force: number | null;
  score_synergie_brut: number;
  score_synergie: number;
  score_final: number;
  champions: ChampionForceDetail[];
  attribute_profile: AttributeProfile;
  meraki_roles: MerakiRoleCount[];
  force_partial?: boolean;
  synergy_insight: TeamSynergyInsight;
}

export interface PredictResponse {
  mode?: PredictionMode;
  blue_win_probability: number;
  red_win_probability: number;
  blue: TeamPredictionDetail;
  red: TeamPredictionDetail;
  differential: AttributeProfile;
  duo_synergies?: SideDuoSynergies;
  bot_lane_matchup?: BotLaneMatchupDetail;
  jungle_support_matchup?: DuoMatchupDetail;
  duo_differential?: DuoDifferential;
  warnings: string[];
}

export interface PickSuggestion {
  champion: string;
  win_probability: number;
  gain_percentage_points: number;
  delta_force: number;
  delta_synergie: number;
  delta_duo: number;
  delta_total: number;
  reason: string;
}

export interface SuggestPickResponse {
  team_side: "blue" | "red";
  role: Role;
  current_win_probability: number | null;
  suggestions: PickSuggestion[];
}

export interface BanSuggestion {
  champion: string;
  best_opponent_role: Role;
  opponent_win_probability: number;
  threat_percentage_points: number;
  delta_force: number;
  delta_synergie: number;
  delta_duo: number;
  delta_total: number;
  reason: string;
}

export interface SuggestBanResponse {
  team_side: "blue" | "red";
  baseline_opponent_win_probability: number | null;
  suggestions: BanSuggestion[];
}

export interface RetrospectiveBanSuggestion {
  champion: string;
  role: Role;
  replacement_champion: string;
  win_probability: number;
  gain_percentage_points: number;
  delta_force: number;
  delta_synergie: number;
  delta_duo: number;
  delta_total: number;
  reason: string;
}

export interface SuggestRetrospectiveBanResponse {
  team_side: "blue" | "red";
  current_win_probability: number | null;
  suggestions: RetrospectiveBanSuggestion[];
}

export interface RetrospectivePickSuggestion {
  role: Role;
  current_champion: string;
  champion: string;
  win_probability: number;
  gain_percentage_points: number;
  delta_force: number;
  delta_synergie: number;
  delta_duo: number;
  delta_total: number;
  reason: string;
}

export interface SuggestRetrospectivePickResponse {
  team_side: "blue" | "red";
  current_win_probability: number | null;
  suggestions: RetrospectivePickSuggestion[];
}

export interface PredictRequest {
  blue_team: DraftPick[];
  red_team: DraftPick[];
  patch: string;
  mode?: PredictionMode;
}

export const INSUFFICIENT_DATA_LABEL =
  "Données pro insuffisantes pour ce champion/duo sur les patchs disponibles";

export const ATTRIBUTE_KEYS = [
  "damage_mean",
  "toughness_mean",
  "control_mean",
  "mobility_mean",
  "utility_mean",
] as const;

export const ATTRIBUTE_LABELS: Record<(typeof ATTRIBUTE_KEYS)[number], string> = {
  damage_mean: "Dégâts",
  toughness_mean: "Robustesse",
  control_mean: "Contrôle",
  mobility_mean: "Mobilité",
  utility_mean: "Utilité",
};

export function emptyBotLaneMatchup(): BotLaneMatchupDetail {
  return {
    blue_champions: [],
    red_champions: [],
    blue_win_probability: 0.5,
    games: 0,
    is_fallback: true,
    method: "soloq_composite",
  };
}

export const emptyDuoMatchup = emptyBotLaneMatchup;

export function emptyDuoSynergyDetail(): DuoSynergyDetail {
  return {
    champions: [],
    score: 0.5,
    games: 0,
    is_fallback: true,
    insufficient_data: false,
  };
}

export function emptyTeamDuoSynergies(): TeamDuoSynergies {
  return {
    duo_jungle_support: emptyDuoSynergyDetail(),
    duo_bot_lane: emptyDuoSynergyDetail(),
  };
}

export function emptyDuoDifferential(): DuoDifferential {
  return {
    jungle_support_advantage: { stronger_side: "even", difference: 0, insufficient_data: false },
    bot_lane_advantage: { stronger_side: "even", difference: 0, insufficient_data: false },
  };
}

export function emptySynergyInsight(): TeamSynergyInsight {
  const placeholder: SynergyContribution = {
    champion: "—",
    role: "TOP",
    marginal_points: 0,
  };
  return {
    contributions: [],
    top_contributor: placeholder,
    least_contributor: placeholder,
  };
}

export function emptyTeamDetail(): TeamPredictionDetail {
  return {
    score_force: 0,
    score_synergie_brut: 0.5,
    score_synergie: 0.5,
    score_final: 0,
    champions: [],
    attribute_profile: {
      damage_mean: 0,
      toughness_mean: 0,
      control_mean: 0,
      mobility_mean: 0,
      utility_mean: 0,
    },
    meraki_roles: [],
    synergy_insight: emptySynergyInsight(),
  };
}

export function normalizePredictResponse(result: PredictResponse): PredictResponse {
  return {
    ...result,
    blue: {
      ...emptyTeamDetail(),
      ...result.blue,
      champions: result.blue.champions ?? [],
      attribute_profile: {
        ...emptyTeamDetail().attribute_profile,
        ...result.blue.attribute_profile,
      },
      meraki_roles: result.blue.meraki_roles ?? [],
      synergy_insight: result.blue.synergy_insight ?? emptySynergyInsight(),
    },
    red: {
      ...emptyTeamDetail(),
      ...result.red,
      champions: result.red.champions ?? [],
      attribute_profile: {
        ...emptyTeamDetail().attribute_profile,
        ...result.red.attribute_profile,
      },
      meraki_roles: result.red.meraki_roles ?? [],
      synergy_insight: result.red.synergy_insight ?? emptySynergyInsight(),
    },
    differential: {
      ...emptyTeamDetail().attribute_profile,
      ...result.differential,
    },
    duo_synergies: result.duo_synergies ?? {
      blue: emptyTeamDuoSynergies(),
      red: emptyTeamDuoSynergies(),
    },
    duo_differential: result.duo_differential ?? emptyDuoDifferential(),
    bot_lane_matchup: result.bot_lane_matchup ?? emptyBotLaneMatchup(),
    jungle_support_matchup: result.jungle_support_matchup ?? emptyDuoMatchup(),
  };
}
