import type { DraftPick, Role } from "../types/draft";
import type {
  MatchSimulationResolveResponse,
  MatchSimulationResult,
  MatchSimulationStartResponse,
  WorldsRoster,
  WorldsStartResponse,
} from "../types/worlds";
import type { PredictionMode, PredictResponse, SuggestBanResponse, SuggestPickResponse, SuggestRetrospectiveBanResponse, SuggestRetrospectivePickResponse } from "../types/predict";
import { fetchChampionPositionsFromMeraki } from "../utils/championPositions";

export interface ChampionsCatalog {
  champions: string[];
  positions: Record<string, Role[]>;
  estimatedChampions: string[];
}

export interface AskChatbotRulesResponse {
  answer: string;
  intent_detected: string;
}

export interface DraftBotMoveResponse {
  action: "ban" | "pick";
  champion: string;
  role?: DraftPick["role"];
  reason?: string | null;
}

export interface MetaStatusResponse {
  latest_patch: string;
  patches_available: string[];
  data_built_at?: string | null;
  oracle_updated_at?: string | null;
  oracle_status?: string | null;
  oracle_team_games?: number | null;
  meraki_updated_at?: string | null;
  meraki_champion_count?: number | null;
  ddragon_version?: string | null;
  ddragon_updated_at?: string | null;
  estimated_champions: string[];
  unmapped_champions: string[];
  schema_version: number;
}

export interface BotExplanationStep {
  champion: string | null;
  role?: DraftPick["role"] | null;
  text: string;
}

export interface BotExplanationResponse {
  steps: BotExplanationStep[];
}

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "/api";

function networkErrorMessage(): string {
  const base = API_BASE_URL;
  if (base.startsWith("http://localhost") || base.startsWith("http://127.0.0.1")) {
    return "API locale injoignable. Lance : uvicorn api:app --reload --port 8001";
  }
  return "API injoignable. Réessaie dans un instant.";
}

export async function fetchChampionsFromApi(): Promise<ChampionsCatalog> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/champions`);
  } catch {
    throw new Error(networkErrorMessage());
  }

  if (!response.ok) {
    throw new Error(`Impossible de charger les champions (HTTP ${response.status})`);
  }

  const data = (await response.json()) as {
    champions: string[];
    positions?: Record<string, Role[]>;
    estimated_champions?: string[];
  };
  if (!Array.isArray(data.champions) || data.champions.length === 0) {
    throw new Error("La liste des champions renvoyée par l'API est vide");
  }

  let positions = data.positions ?? {};
  if (Object.keys(positions).length === 0) {
    try {
      positions = await fetchChampionPositionsFromMeraki();
    } catch {
      // L'API locale est peut-être ancienne ; on continue sans positions distantes.
    }
  }

  return {
    champions: data.champions,
    positions,
    estimatedChampions: data.estimated_champions ?? [],
  };
}
export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

export async function fetchMetaStatus(): Promise<MetaStatusResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/meta/status`);
  } catch {
    throw new Error(networkErrorMessage());
  }

  if (!response.ok) {
    throw new Error(`Statut data indisponible (HTTP ${response.status})`);
  }

  return (await response.json()) as MetaStatusResponse;
}

export async function predictDraft(
  blueTeam: DraftPick[],
  redTeam: DraftPick[],
  patch: string,
  mode: PredictionMode = "mixed",
): Promise<PredictResponse> {
  const payload = {
    blue_team: blueTeam,
    red_team: redTeam,
    patch,
    mode,
  };

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(networkErrorMessage());
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const message =
      typeof detail === "object" && detail && "detail" in detail
        ? String(detail.detail)
        : `HTTP ${response.status}`;
    throw new Error(`Prédiction impossible : ${message}`);
  }

  return (await response.json()) as PredictResponse;
}

async function getJson<T>(path: string, errorPrefix: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`);
  } catch {
    throw new Error(networkErrorMessage());
  }

  if (!response.ok) {
    throw new Error(`${errorPrefix} (HTTP ${response.status})`);
  }

  return (await response.json()) as T;
}

async function postJson<T>(path: string, payload: unknown, errorPrefix: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(networkErrorMessage());
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const message =
      typeof detail === "object" && detail && "detail" in detail
        ? String(detail.detail)
        : `HTTP ${response.status}`;
    throw new Error(`${errorPrefix} : ${message}`);
  }

  return (await response.json()) as T;
}

export async function suggestPick(
  teamSide: "blue" | "red",
  teamPicks: DraftPick[],
  opponentPicks: DraftPick[],
  roleToImprove: Role,
  patch: string,
  availableChampions: string[],
  mode: PredictionMode = "mixed",
): Promise<SuggestPickResponse> {
  return postJson<SuggestPickResponse>(
    "/suggest-pick",
    {
      team_side: teamSide,
      team_picks: teamPicks,
      opponent_picks: opponentPicks,
      role_to_improve: roleToImprove,
      patch,
      available_champions: availableChampions,
      mode,
    },
    "Suggestion de pick impossible",
  );
}

export async function suggestBan(
  teamSide: "blue" | "red",
  teamPicks: DraftPick[],
  opponentPicks: DraftPick[],
  opponentRemainingRoles: Role[],
  patch: string,
  availableChampions: string[],
  mode: PredictionMode = "mixed",
): Promise<SuggestBanResponse> {
  return postJson<SuggestBanResponse>(
    "/suggest-ban",
    {
      team_side: teamSide,
      team_picks: teamPicks,
      opponent_picks: opponentPicks,
      opponent_remaining_roles: opponentRemainingRoles,
      patch,
      available_champions: availableChampions,
      mode,
    },
    "Suggestion de ban impossible",
  );
}

export async function suggestRetrospectiveBan(
  teamSide: "blue" | "red",
  teamPicks: DraftPick[],
  opponentPicks: DraftPick[],
  patch: string,
  availableChampions: string[],
  mode: PredictionMode = "mixed",
): Promise<SuggestRetrospectiveBanResponse> {
  return postJson<SuggestRetrospectiveBanResponse>(
    "/suggest-retrospective-ban",
    {
      team_side: teamSide,
      team_picks: teamPicks,
      opponent_picks: opponentPicks,
      patch,
      available_champions: availableChampions,
      mode,
    },
    "Analyse des bans manqués impossible",
  );
}

export async function suggestRetrospectivePick(
  teamSide: "blue" | "red",
  teamPicks: DraftPick[],
  opponentPicks: DraftPick[],
  patch: string,
  availableChampions: string[],
  mode: PredictionMode = "mixed",
): Promise<SuggestRetrospectivePickResponse> {
  return postJson<SuggestRetrospectivePickResponse>(
    "/suggest-retrospective-pick",
    {
      team_side: teamSide,
      team_picks: teamPicks,
      opponent_picks: opponentPicks,
      patch,
      available_champions: availableChampions,
      mode,
      picks_per_role: 3,
    },
    "Analyse des picks manqués impossible",
  );
}

export async function draftBotMove(
  actionType: "ban" | "pick",
  botSide: "blue" | "red",
  botPicks: DraftPick[],
  opponentPicks: DraftPick[],
  patch: string,
  availableChampions: string[],
  mode: PredictionMode = "mixed",
): Promise<DraftBotMoveResponse> {
  return postJson<DraftBotMoveResponse>(
    "/draft-bot/move",
    {
      action_type: actionType,
      bot_side: botSide,
      bot_picks: botPicks.map((pick) => ({ champion: pick.champion })),
      opponent_picks: opponentPicks.map((pick) => ({ champion: pick.champion })),
      patch,
      available_champions: availableChampions,
      mode,
    },
    "Tour du bot impossible",
  );
}

export async function fetchBotExplanation(
  botPicks: DraftPick[],
  opponentPicks: DraftPick[],
  patch: string,
  mode: PredictionMode = "pro",
): Promise<BotExplanationResponse> {
  return postJson<BotExplanationResponse>(
    "/bot-explanation",
    {
      bot_picks: botPicks,
      opponent_picks: opponentPicks,
      patch,
      mode,
    },
    "Explication des choix impossible",
  );
}

export async function askChatbotRules(
  question: string,
  predictionContext: Record<string, unknown>,
  availableChampions: string[],
): Promise<AskChatbotRulesResponse> {
  return postJson<AskChatbotRulesResponse>(
    "/ask-chatbot-rules",
    {
      question,
      prediction_context: predictionContext,
      available_champions: availableChampions,
    },
    "Question au chatbot impossible",
  );
}

export async function fetchWorldsTeams(): Promise<{ teams: WorldsStartResponse["opponent_teams"] }> {
  return getJson("/worlds/teams", "Impossible de charger les équipes Worlds");
}

export async function startWorldsTournament(
  teamName: string,
  coachName: string,
  roster: WorldsRoster,
): Promise<WorldsStartResponse> {
  return postJson<WorldsStartResponse>(
    "/worlds/start",
    {
      team_name: teamName,
      coach_name: coachName,
      roster,
    },
    "Impossible de démarrer le tournoi Worlds",
  );
}

export async function worldsDraftBotMove(
  actionType: "ban" | "pick",
  botSide: "blue" | "red",
  botPicks: DraftPick[],
  opponentPicks: DraftPick[],
  patch: string,
  availableChampions: string[],
  teamId: string,
  teamRoster: WorldsRoster,
): Promise<DraftBotMoveResponse> {
  return postJson<DraftBotMoveResponse>(
    "/worlds/draft-bot/move",
    {
      action_type: actionType,
      bot_side: botSide,
      bot_picks: botPicks.map((pick) => ({ champion: pick.champion })),
      opponent_picks: opponentPicks.map((pick) => ({ champion: pick.champion })),
      patch,
      available_champions: availableChampions,
      mode: "pro",
      team_id: teamId,
      team_roster: teamRoster,
    },
    "Tour du bot Worlds impossible",
  );
}

function buildSimulationPredictionSnapshot(prediction: PredictResponse) {
  return {
    blue_win_probability: prediction.blue_win_probability,
    bot_lane_matchup: prediction.bot_lane_matchup ?? null,
    jungle_support_matchup: prediction.jungle_support_matchup ?? null,
    blue: {
      score_final: prediction.blue.score_final,
      score_synergie: prediction.blue.score_synergie,
      champions: prediction.blue.champions,
    },
    red: {
      score_final: prediction.red.score_final,
      score_synergie: prediction.red.score_synergie,
      champions: prediction.red.champions,
    },
  };
}

export async function startWorldsSimulation(
  playerSide: "blue" | "red",
  playerTeamName: string,
  opponentTeamName: string,
  prediction: PredictResponse,
  opponentTeamId?: string,
  playerRoster?: WorldsRoster,
  opponentRoster?: WorldsRoster,
): Promise<MatchSimulationStartResponse> {
  return postJson<MatchSimulationStartResponse>(
    "/worlds/simulate-match",
    {
      action: "start",
      player_side: playerSide,
      player_team_name: playerTeamName,
      opponent_team_name: opponentTeamName,
      draft_blue_win_probability: prediction.blue_win_probability,
      prediction: buildSimulationPredictionSnapshot(prediction),
      opponent_team_id: opponentTeamId,
      player_roster: playerRoster,
      opponent_roster: opponentRoster,
    },
    "Impossible de démarrer la simulation",
  );
}

export async function resolveWorldsSimulationPhase(
  simulationId: string,
  phase: "early" | "mid",
  choice: "engage" | "temporize",
): Promise<MatchSimulationResolveResponse> {
  return postJson<MatchSimulationResolveResponse>(
    "/worlds/simulate-match",
    {
      action: "resolve",
      simulation_id: simulationId,
      phase,
      choice,
    },
    "Impossible de résoudre la phase de simulation",
  );
}

/** @deprecated Utiliser startWorldsSimulation + resolveWorldsSimulationPhase. */
export async function simulateWorldsMatch(
  playerSide: "blue" | "red",
  playerTeamName: string,
  opponentTeamName: string,
  draftBlueWinProbability: number,
  opponentTeamId?: string,
  playerRoster?: WorldsRoster,
  opponentRoster?: WorldsRoster,
): Promise<MatchSimulationResult> {
  const started = await startWorldsSimulation(
    playerSide,
    playerTeamName,
    opponentTeamName,
    {
      blue_win_probability: draftBlueWinProbability,
      red_win_probability: 1 - draftBlueWinProbability,
      blue: {
        score_final: 0,
        score_synergie: 0.5,
        score_synergie_brut: 0.5,
        score_force: null,
        champions: [],
        attribute_profile: {
          damage_mean: 0,
          toughness_mean: 0,
          control_mean: 0,
          mobility_mean: 0,
          utility_mean: 0,
        },
        meraki_roles: [],
        synergy_insight: {
          contributions: [],
          top_contributor: { champion: "", role: "TOP", marginal_points: 0 },
          least_contributor: { champion: "", role: "TOP", marginal_points: 0 },
        },
      },
      red: {
        score_final: 0,
        score_synergie: 0.5,
        score_synergie_brut: 0.5,
        score_force: null,
        champions: [],
        attribute_profile: {
          damage_mean: 0,
          toughness_mean: 0,
          control_mean: 0,
          mobility_mean: 0,
          utility_mean: 0,
        },
        meraki_roles: [],
        synergy_insight: {
          contributions: [],
          top_contributor: { champion: "", role: "TOP", marginal_points: 0 },
          least_contributor: { champion: "", role: "TOP", marginal_points: 0 },
        },
      },
      differential: {
        damage_mean: 0,
        toughness_mean: 0,
        control_mean: 0,
        mobility_mean: 0,
        utility_mean: 0,
      },
      warnings: [],
    },
    opponentTeamId,
    playerRoster,
    opponentRoster,
  );
  await resolveWorldsSimulationPhase(started.simulation_id, "early", "engage");
  const final = await resolveWorldsSimulationPhase(started.simulation_id, "mid", "engage");
  return {
    player_wins: Boolean(final.player_wins),
    player_win_probability: final.player_win_probability ?? started.player_win_probability,
    draft_blue_win_probability:
      final.draft_blue_win_probability ?? started.draft_blue_win_probability,
    winner_side: final.winner_side ?? "blue",
    winner_team_name: final.winner_team_name ?? playerTeamName,
    loser_team_name: final.loser_team_name ?? opponentTeamName,
    blue_win_probability: final.blue_win_probability ?? draftBlueWinProbability,
    events: final.events ?? [],
    game_length_minutes: final.game_length_minutes ?? 38,
    phases_won: final.phases_won,
  };
}
