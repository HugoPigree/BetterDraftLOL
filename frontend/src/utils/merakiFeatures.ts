const MERAKI_URL =
  "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions.json";

export const MERAKI_ATTRIBUTES = [
  "damage",
  "toughness",
  "control",
  "mobility",
  "utility",
] as const;

export type MerakiAttribute = (typeof MERAKI_ATTRIBUTES)[number];

export interface MerakiAttributeRatings {
  damage: number;
  toughness: number;
  control: number;
  mobility: number;
  utility: number;
}

export interface MerakiChampionProfile {
  key: string;
  name: string;
  attributeRatings: MerakiAttributeRatings;
  roles: string[];
}

export type MerakiChampionCatalog = Map<string, MerakiChampionProfile>;

let catalogPromise: Promise<MerakiChampionCatalog> | null = null;

function normalizeName(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function parseRatings(raw: unknown): MerakiAttributeRatings {
  const ratings = (raw ?? {}) as Record<string, unknown>;
  const fallback = 1.5;

  return {
    damage: Number(ratings.damage ?? fallback),
    toughness: Number(ratings.toughness ?? fallback),
    control: Number(ratings.control ?? fallback),
    mobility: Number(ratings.mobility ?? fallback),
    utility: Number(ratings.utility ?? fallback),
  };
}

function indexProfile(catalog: MerakiChampionCatalog, profile: MerakiChampionProfile): void {
  catalog.set(profile.key, profile);
  catalog.set(profile.name, profile);
  catalog.set(normalizeName(profile.key), profile);
  catalog.set(normalizeName(profile.name), profile);
}

export async function loadMerakiChampionCatalog(): Promise<MerakiChampionCatalog> {
  if (catalogPromise) {
    return catalogPromise;
  }

  catalogPromise = (async () => {
    const response = await fetch(MERAKI_URL);
    if (!response.ok) {
      throw new Error(`Meraki champions HTTP ${response.status}`);
    }

    const payload = (await response.json()) as Record<
      string,
      {
        name?: string;
        roles?: string[];
        attributeRatings?: Record<string, number>;
      }
    >;

    const catalog: MerakiChampionCatalog = new Map();

    for (const [key, champion] of Object.entries(payload)) {
      const profile: MerakiChampionProfile = {
        key,
        name: String(champion.name ?? key),
        attributeRatings: parseRatings(champion.attributeRatings),
        roles: Array.isArray(champion.roles) ? champion.roles.map(String) : [],
      };
      indexProfile(catalog, profile);
    }

    return catalog;
  })();

  return catalogPromise;
}

export function resolveMerakiChampionProfile(
  championName: string,
  catalog: MerakiChampionCatalog,
): MerakiChampionProfile | null {
  const trimmed = championName.trim();
  return catalog.get(trimmed) ?? catalog.get(normalizeName(trimmed)) ?? null;
}

export function averageDuoAttributes(
  champions: string[],
  catalog: MerakiChampionCatalog,
): MerakiAttributeRatings | null {
  const profiles = champions
    .map((champion) => resolveMerakiChampionProfile(champion, catalog))
    .filter((profile): profile is MerakiChampionProfile => profile !== null);

  if (profiles.length !== champions.length) {
    return null;
  }

  const totals: MerakiAttributeRatings = {
    damage: 0,
    toughness: 0,
    control: 0,
    mobility: 0,
    utility: 0,
  };

  for (const profile of profiles) {
    for (const attribute of MERAKI_ATTRIBUTES) {
      totals[attribute] += profile.attributeRatings[attribute];
    }
  }

  const count = profiles.length;
  return {
    damage: totals.damage / count,
    toughness: totals.toughness / count,
    control: totals.control / count,
    mobility: totals.mobility / count,
    utility: totals.utility / count,
  };
}
