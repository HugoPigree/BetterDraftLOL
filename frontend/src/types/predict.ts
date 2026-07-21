import type { DraftPick } from "./draft";

export interface ChampionForceDetail {
  champion: string;
  role: DraftPick["role"];
  winrate: number;
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

export interface TeamPredictionDetail {
  score_force: number;
  score_synergie_brut: number;
  score_synergie: number;
  score_final: number;
  champions: ChampionForceDetail[];
  attribute_profile: AttributeProfile;
  meraki_roles: MerakiRoleCount[];
}

export interface PredictResponse {
  blue_win_probability: number;
  red_win_probability: number;
  blue: TeamPredictionDetail;
  red: TeamPredictionDetail;
  differential: AttributeProfile;
  warnings: string[];
}

export interface PredictRequest {
  blue_team: DraftPick[];
  red_team: DraftPick[];
  patch: string;
}

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
    },
    differential: {
      ...emptyTeamDetail().attribute_profile,
      ...result.differential,
    },
  };
}
