import type { DraftPick, Role } from "../types/draft";
import type { PredictResponse } from "../types/predict";
import { fetchChampionPositionsFromMeraki } from "../utils/championPositions";

export interface ChampionsCatalog {
  champions: string[];
  positions: Record<string, Role[]>;
}

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "/api";

export async function fetchChampionsFromApi(): Promise<ChampionsCatalog> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/champions`);
  } catch {
    throw new Error(
      "Impossible de joindre l'API locale. Lance : uvicorn api:app --reload --port 8000",
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
): Promise<PredictResponse> {
  const payload = {
    blue_team: blueTeam,
    red_team: redTeam,
    patch,
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
      "Impossible de joindre l'API locale. Lance : uvicorn api:app --reload --port 8000",
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
