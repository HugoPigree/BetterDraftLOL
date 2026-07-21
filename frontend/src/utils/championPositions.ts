import type { Role } from "../types/draft";

const MERAKI_URL =
  "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions.json";

const POSITION_MAP: Record<string, Role> = {
  TOP: "TOP",
  JUNGLE: "JUNGLE",
  MIDDLE: "MIDDLE",
  BOTTOM: "BOTTOM",
  SUPPORT: "UTILITY",
};

function mapPositions(rawPositions: unknown): Role[] {
  if (!Array.isArray(rawPositions)) {
    return [];
  }

  const mapped: Role[] = [];
  for (const position of rawPositions) {
    const role = POSITION_MAP[String(position).toUpperCase()];
    if (role && !mapped.includes(role)) {
      mapped.push(role);
    }
  }
  return mapped;
}

export function buildPositionsCatalog(
  merakiChampions: Record<string, { name?: string; positions?: string[] }>,
): Record<string, Role[]> {
  const catalog: Record<string, Role[]> = {};

  for (const [key, payload] of Object.entries(merakiChampions)) {
    const name = String(payload.name ?? key).trim();
    if (!name) {
      continue;
    }
    catalog[name] = mapPositions(payload.positions);
  }

  return catalog;
}

export async function fetchChampionPositionsFromMeraki(): Promise<Record<string, Role[]>> {
  try {
    const response = await fetch(MERAKI_URL);
    if (response.ok) {
      const merakiChampions = (await response.json()) as Record<
        string,
        { name?: string; positions?: string[] }
      >;
      return buildPositionsCatalog(merakiChampions);
    }
  } catch {
    // fallback below
  }

  const localResponse = await fetch("/champion-positions.json");
  if (!localResponse.ok) {
    throw new Error("Impossible de charger les positions des champions");
  }

  const localCatalog = (await localResponse.json()) as Record<string, Role[]>;
  return localCatalog;
}
