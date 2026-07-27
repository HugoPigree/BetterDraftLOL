export type LecUpgradeKey = "scouting" | "infrastructure" | "clutch";

export interface LecWeeklyEvent {
  id: string;
  title: string;
  description: string;
  powerBonus: number;
  clutchBonus: number;
}

export interface LecCareerProgress {
  upgradePoints: number;
  upgrades: Record<LecUpgradeKey, number>;
  weeklyEvent: LecWeeklyEvent | null;
  winStreak: number;
}

export const MAX_UPGRADE_LEVEL = 3;

export const UPGRADE_DETAILS: Record<
  LecUpgradeKey,
  { label: string; description: string }
> = {
  scouting: {
    label: "Scouting",
    description: "Adversaire moins prévisible en draft (plus de variété).",
  },
  infrastructure: {
    label: "Infrastructure",
    description: "+puissance roster en simulation.",
  },
  clutch: {
    label: "Clutch",
    description: "+edge sur les décisions engage/temporize.",
  },
};

const WEEKLY_EVENTS: Omit<LecWeeklyEvent, "id">[] = [
  {
    title: "Meta shift",
    description: "La patch bouge — votre staff s'adapte plus vite.",
    powerBonus: 0.02,
    clutchBonus: 0.0,
  },
  {
    title: "Hot hand",
    description: "Les joueurs sont chauds cette semaine.",
    powerBonus: 0.03,
    clutchBonus: 0.02,
  },
  {
    title: "Adversaire en slump",
    description: "Rumeurs de mauvaise prep chez l'adversaire.",
    powerBonus: 0.025,
    clutchBonus: 0.0,
  },
  {
    title: "Draft marathon",
    description: "Beaucoup de scrims — meilleure lecture des patterns.",
    powerBonus: 0.0,
    clutchBonus: 0.03,
  },
  {
    title: "Fatigue travel",
    description: "Semaine chargée — marge d'erreur réduite.",
    powerBonus: -0.015,
    clutchBonus: -0.01,
  },
];

export function createDefaultProgress(): LecCareerProgress {
  return {
    upgradePoints: 0,
    upgrades: { scouting: 0, infrastructure: 0, clutch: 0 },
    weeklyEvent: null,
    winStreak: 0,
  };
}

function hashString(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function rollWeeklyEvent(week: number, seasonSeed: string): LecWeeklyEvent {
  const index = hashString(`${seasonSeed}:${week}`) % WEEKLY_EVENTS.length;
  const event = WEEKLY_EVENTS[index] ?? WEEKLY_EVENTS[0];
  return { id: `week-${week}-${event.title}`, ...event };
}

export function awardProgressAfterMatch(
  progress: LecCareerProgress,
  playerWon: boolean,
): LecCareerProgress {
  const winStreak = playerWon ? progress.winStreak + 1 : 0;
  const bonusPoint = playerWon && winStreak >= 2 ? 1 : 0;
  return {
    ...progress,
    winStreak,
    upgradePoints: progress.upgradePoints + (playerWon ? 1 : 0) + bonusPoint,
  };
}

export function spendUpgradePoint(
  progress: LecCareerProgress,
  key: LecUpgradeKey,
): LecCareerProgress | null {
  if (progress.upgradePoints <= 0) {
    return null;
  }
  if (progress.upgrades[key] >= MAX_UPGRADE_LEVEL) {
    return null;
  }
  return {
    ...progress,
    upgradePoints: progress.upgradePoints - 1,
    upgrades: {
      ...progress.upgrades,
      [key]: progress.upgrades[key] + 1,
    },
  };
}

export function simulationPowerBonus(progress: LecCareerProgress): number {
  const infra = progress.upgrades.infrastructure * 0.015;
  const event = progress.weeklyEvent?.powerBonus ?? 0;
  const streak = Math.min(progress.winStreak, 3) * 0.005;
  return infra + event + streak;
}

export function simulationClutchBonus(progress: LecCareerProgress): number {
  const clutch = progress.upgrades.clutch * 0.02;
  const event = progress.weeklyEvent?.clutchBonus ?? 0;
  return clutch + event;
}

export function scoutingDraftSeedSalt(progress: LecCareerProgress): string {
  return `:scouting:${progress.upgrades.scouting}`;
}
