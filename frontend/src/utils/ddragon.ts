const CHAMPION_ID_MAP: Record<string, string> = {
  "Wukong": "MonkeyKing",
  "Monkey King": "MonkeyKing",
  "Nunu & Willump": "Nunu",
  "Nunu and Willump": "Nunu",
  "Renata Glasc": "Renata",
  "Dr. Mundo": "DrMundo",
  "Miss Fortune": "MissFortune",
  "Jarvan IV": "JarvanIV",
  "Twisted Fate": "TwistedFate",
  "Xin Zhao": "XinZhao",
  "Lee Sin": "LeeSin",
  "Master Yi": "MasterYi",
  "Aurelion Sol": "AurelionSol",
  "Cho'Gath": "Chogath",
  "Kai'Sa": "Kaisa",
  "Kha'Zix": "Khazix",
  "Rek'Sai": "RekSai",
  "Vel'Koz": "Velkoz",
  "Bel'Veth": "Belveth",
  "Kog'Maw": "KogMaw",
  "Tahm Kench": "TahmKench",
  "LeBlanc": "Leblanc",
};

const VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json";

export async function fetchLatestDdragonVersion(): Promise<string> {
  const response = await fetch(VERSIONS_URL);
  if (!response.ok) {
    throw new Error(`Impossible de charger les versions Data Dragon (${response.status})`);
  }

  const versions = (await response.json()) as string[];
  if (!versions.length) {
    throw new Error("Aucune version Data Dragon disponible");
  }

  return versions[0];
}

export function toChampionId(championName: string): string {
  if (CHAMPION_ID_MAP[championName]) {
    return CHAMPION_ID_MAP[championName];
  }

  return championName.replace(/[\s.'&-]/g, "");
}

export function getChampionIconUrl(championName: string, version: string): string {
  const championId = toChampionId(championName);
  return `https://ddragon.leagueoflegends.com/cdn/${version}/img/champion/${championId}.png`;
}

export function getChampionSplashUrl(championName: string, skinNum = 0): string {
  const championId = toChampionId(championName);
  return `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${championId}_${skinNum}.jpg`;
}
