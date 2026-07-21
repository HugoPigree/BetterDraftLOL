import type { DraftPick, Role } from "../types/draft";
import type { PredictionMode, PredictResponse, SuggestBanResponse, SuggestPickResponse, SuggestRetrospectiveBanResponse, SuggestRetrospectivePickResponse } from "../types/predict";
import { fetchChampionPositionsFromMeraki } from "../utils/championPositions";

export interface ChampionsCatalog {
  champions: string[];
  positions: Record<string, Role[]>;
}

export interface AskChatbotRulesResponse {
  answer: string;
  intent_detected: string;
}

export interface DraftBotMoveResponse {
  action: "ban" | "pick";
  champion: string;
  role?: DraftPick["role"];
}

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "/api";

export async function fetchChampionsFromApi(): Promise<ChampionsCatalog> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/champions`);
  } catch {
    throw new Error(
      "Impossible de joindre l'API locale. Lance : uvicorn api:app --reload --port 8001",
    );
  }

  if (!response.ok) {
    throw new Error(`Impossible de charger les champions (HTTP ${response.status})`);
  }

  const data = (await response.json()) as { champions: string[]; positions?: Record<string, Role[]> };
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
    throw new Error(
      "Impossible de joindre l'API locale. Lance : uvicorn api:app --reload --port 8001",
    );
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

async function postJson<T>(path: string, payload: unknown, errorPrefix: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      "Impossible de joindre l'API locale. Lance : uvicorn api:app --reload --port 8001",
    );
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
      bot_picks: botPicks,
      opponent_picks: opponentPicks,
      patch,
      available_champions: availableChampions,
      mode,
    },
    "Tour du bot impossible",
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
