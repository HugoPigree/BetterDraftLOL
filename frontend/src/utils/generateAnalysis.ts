import type { Role } from "../types/draft";
import type { PredictResponse, PredictionMode, TeamPredictionDetail } from "../types/predict";
import { INSUFFICIENT_DATA_LABEL } from "../types/predict";
import { ATTRIBUTE_LABELS } from "../types/predict";

const WEIGHT_FORCE = 0.5;
const WEIGHT_SYNERGY = 0.4;

const ROLE_LABELS: Record<Role, string> = {
  TOP: "top",
  JUNGLE: "jungle",
  MIDDLE: "mid",
  BOTTOM: "adc",
  UTILITY: "support",
};

const MERAKI_ROLE_LABELS: Record<string, string> = {
  FIGHTER: "combattant",
  TANK: "tank",
  MAGE: "mage",
  ASSASSIN: "assassin",
  MARKSMAN: "tireur",
  VANGUARD: "gardien",
  JUGGERNAUT: "juggernaut",
  DIVER: "diver",
  BURST: "burst",
  ENCHANTER: "enchanter",
  CATCHER: "catch",
  SPECIALIST: "spécialiste",
  ARTILLERY: "artillerie",
  BATTLEMAGE: "battle mage",
  SKIRMISHER: "skirmisher",
  WARDEN: "warden",
};

const FACTOR_LABELS: Record<string, Record<"force" | "synergie" | "side", string>> = {
  mixed: {
    force: "la force individuelle (winrates solo queue)",
    synergie: "l'affinité de composition",
    side: "l'avantage de side blue",
  },
  pro: {
    force: "la force individuelle (winrates pro Oracle's Elixir)",
    synergie: "l'affinité de composition",
    side: "l'avantage de side blue",
  },
};

export interface ScoreExplanation {
  label: string;
  value: string;
  hint: string;
}

export interface TeamAffinityInsight {
  title: string;
  lines: string[];
}

export interface LaneMatchupInsight {
  role: Role;
  roleLabel: string;
  blueChampion: string;
  redChampion: string;
  blueWinrate: number;
  redWinrate: number;
  deltaPoints: number;
  summary: string;
}

export interface DraftAnalysisBundle {
  summary: string[];
  blueAffinity: TeamAffinityInsight;
  redAffinity: TeamAffinityInsight;
  laneMatchups: LaneMatchupInsight[];
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatDeltaPoints(value: number): string {
  const points = value * 100;
  const sign = points > 0 ? "+" : "";
  return `${sign}${points.toFixed(1)} pt`;
}

function teamLabel(side: "blue" | "red"): string {
  return side === "blue" ? "blue" : "red";
}

function translateMerakiRole(role: string): string {
  return MERAKI_ROLE_LABELS[role] ?? role.toLowerCase();
}

function averageWinrate(champions: TeamPredictionDetail["champions"]): number | null {
  const valid = champions.filter(
    (champion) => !champion.insufficient_data && champion.winrate !== null,
  );
  if (valid.length === 0) {
    return null;
  }
  return valid.reduce((sum, champion) => sum + (champion.winrate ?? 0), 0) / valid.length;
}

function dominantFactor(result: PredictResponse): keyof typeof FACTOR_LABELS.mixed {
  const blueForce = result.blue.score_force ?? 0.5;
  const redForce = result.red.score_force ?? 0.5;
  const forceDiff = Math.abs(blueForce - redForce);
  const synergyDiff = Math.abs(result.blue.score_synergie - result.red.score_synergie);

  const blueSidePart =
    result.blue.score_final - WEIGHT_FORCE * blueForce - WEIGHT_SYNERGY * result.blue.score_synergie;
  const redSidePart =
    result.red.score_final - WEIGHT_FORCE * redForce - WEIGHT_SYNERGY * result.red.score_synergie;
  const sideDiff = Math.abs(blueSidePart - redSidePart);

  const factors: Array<{ name: keyof typeof FACTOR_LABELS.mixed; diff: number }> = [
    { name: "force", diff: forceDiff },
    { name: "synergie", diff: synergyDiff },
    { name: "side", diff: sideDiff },
  ];

  factors.sort((a, b) => b.diff - a.diff);
  return factors[0]?.name ?? "force";
}

export function explainTeamScores(
  team: TeamPredictionDetail,
  side: "blue" | "red",
  isProMode = false,
): ScoreExplanation[] {
  const sideLabel = side === "blue" ? "blue" : "red";
  const forceLabel = isProMode ? "Force pro" : "Force soloQ";
  const forceValue =
    team.score_force === null
      ? "N/A"
      : formatPercent(team.score_force);
  const forceHint =
    team.score_force === null
      ? INSUFFICIENT_DATA_LABEL
      : team.force_partial
        ? `Winrate pro moyen sur les picks avec assez de games (${formatDeltaPoints(team.score_force - 0.5)} vs 50% neutre).`
        : `Winrate moyen des 5 picks (${formatDeltaPoints(team.score_force - 0.5)} vs 50% neutre).`;

  return [
    {
      label: forceLabel,
      value: forceValue,
      hint: forceHint,
    },
    {
      label: "Affinité compo",
      value: formatPercent(team.score_synergie),
      hint: `Modèle ML sur les archétypes Meraki + attributs (dégâts, contrôle…). ${formatDeltaPoints(team.score_synergie - 0.5)} vs 50% neutre.`,
    },
    {
      label: "Score pondéré",
      value: `${(team.score_final * 100).toFixed(1)} pts`,
      hint: `50% force + 40% affinité + 10% side ${sideLabel}. Sert au calcul final de probabilité.`,
    },
  ];
}

function generateTeamAffinity(team: TeamPredictionDetail, side: "blue" | "red"): TeamAffinityInsight {
  const lines: string[] = [];
  const profile = team.attribute_profile;
  const roles = team.meraki_roles;

  if (roles.length >= 2) {
    const labels = roles
      .slice(0, 3)
      .map((entry) => `${entry.count}× ${translateMerakiRole(entry.role)}`)
      .join(", ");
    lines.push(`Archétypes dominants : ${labels}.`);
  }

  const hasFrontline = roles.some((entry) =>
    ["TANK", "VANGUARD", "WARDEN", "JUGGERNAUT"].includes(entry.role),
  );
  const hasBackline = roles.some((entry) =>
    ["MAGE", "MARKSMAN", "ARTILLERY", "ENCHANTER"].includes(entry.role),
  );

  if (hasFrontline && hasBackline) {
    lines.push("Bonne complémentarité frontline / backline pour engage et dégâts à distance.");
  } else if (!hasFrontline) {
    lines.push("Peu de frontline : la compo peut manquer d'engage naturel et de soak.");
  }

  if (profile.control_mean >= 2.1 && profile.damage_mean >= 2.0) {
    lines.push("Profil engage + follow-up : contrôle et dégâts suffisants pour enchaîner les fights.");
  }

  if (profile.mobility_mean >= 2.2) {
    lines.push("Compo mobile : forte capacité à flank, split ou punir les erreurs de placement.");
  }

  if (profile.toughness_mean <= 1.4) {
    lines.push("Compo fragile : faible robustesse, sensible aux burst et aux hard engages.");
  }

  if (lines.length === 0) {
    lines.push("Profil de compo équilibré sans identité extrême sur un seul axe.");
  }

  return {
    title: side === "blue" ? "Affinité interne — Blue" : "Affinité interne — Red",
    lines: lines.slice(0, 3),
  };
}

function championsByRole(
  team: TeamPredictionDetail,
): Partial<Record<Role, TeamPredictionDetail["champions"][number]>> {
  const map: Partial<Record<Role, TeamPredictionDetail["champions"][number]>> = {};
  for (const champion of team.champions) {
    map[champion.role] = champion;
  }
  return map;
}

export function generateLaneMatchups(
  result: PredictResponse,
  isProMode = false,
): LaneMatchupInsight[] {
  const roles: Role[] = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];
  const blueByRole = championsByRole(result.blue);
  const redByRole = championsByRole(result.red);
  const matchups: LaneMatchupInsight[] = [];
  const wrLabel = isProMode ? "pro" : "soloQ";

  for (const role of roles) {
    const bluePick = blueByRole[role];
    const redPick = redByRole[role];
    if (!bluePick || !redPick) {
      continue;
    }

    if (
      isProMode &&
      (bluePick.insufficient_data ||
        redPick.insufficient_data ||
        bluePick.winrate === null ||
        redPick.winrate === null)
    ) {
      matchups.push({
        role,
        roleLabel: ROLE_LABELS[role],
        blueChampion: bluePick.champion,
        redChampion: redPick.champion,
        blueWinrate: bluePick.winrate ?? 0.5,
        redWinrate: redPick.winrate ?? 0.5,
        deltaPoints: 0,
        summary: `${ROLE_LABELS[role]} : ${INSUFFICIENT_DATA_LABEL}`,
      });
      continue;
    }

    const deltaPoints = ((bluePick.winrate ?? 0.5) - (redPick.winrate ?? 0.5)) * 100;
    const roleLabel = ROLE_LABELS[role];

    let summary: string;
    if (Math.abs(deltaPoints) < 2) {
      summary = `Matchup ${roleLabel} équilibré entre ${bluePick.champion} et ${redPick.champion}.`;
    } else if (deltaPoints > 0) {
      summary = `${bluePick.champion} (${formatPercent(bluePick.winrate ?? 0.5)}) part avec un avantage ${wrLabel} sur ${redPick.champion} (${formatPercent(redPick.winrate ?? 0.5)}) au ${roleLabel}.`;
    } else {
      summary = `${redPick.champion} (${formatPercent(redPick.winrate ?? 0.5)}) part favori ${wrLabel} face à ${bluePick.champion} (${formatPercent(bluePick.winrate ?? 0.5)}) au ${roleLabel}.`;
    }

    matchups.push({
      role,
      roleLabel,
      blueChampion: bluePick.champion,
      redChampion: redPick.champion,
      blueWinrate: bluePick.winrate ?? 0.5,
      redWinrate: redPick.winrate ?? 0.5,
      deltaPoints,
      summary,
    });
  }

  return matchups.sort((a, b) => Math.abs(b.deltaPoints) - Math.abs(a.deltaPoints));
}

export function generateAnalysis(
  result: PredictResponse,
  patch: string,
  mode: PredictionMode = "mixed",
): string[] {
  return generateDraftAnalysis(result, patch, mode).summary;
}

export function generateDraftAnalysis(
  result: PredictResponse,
  patch: string,
  mode: PredictionMode = "mixed",
): DraftAnalysisBundle {
  const isProMode = mode === "pro";
  const factorLabels = FACTOR_LABELS[mode];
  const summary: string[] = [];
  const attributeThreshold = 0.3;
  const winrateThreshold = 0.02;

  for (const key of Object.keys(ATTRIBUTE_LABELS) as Array<keyof typeof ATTRIBUTE_LABELS>) {
    const diff = result.differential[key];
    const label = ATTRIBUTE_LABELS[key].toLowerCase();
    if (Math.abs(diff) > attributeThreshold) {
      const side: "blue" | "red" = diff > 0 ? "blue" : "red";
      summary.push(`L'équipe ${teamLabel(side)} domine sur ${label} dans le profil Meraki.`);
    }
  }

  const blueAvg = averageWinrate(result.blue.champions);
  const redAvg = averageWinrate(result.red.champions);
  const winrateGap =
    blueAvg !== null && redAvg !== null ? Math.abs(blueAvg - redAvg) : 0;

  if (blueAvg !== null && redAvg !== null && winrateGap > winrateThreshold) {
    const strongerSide: "blue" | "red" = blueAvg > redAvg ? "blue" : "red";
    const forceLabel = isProMode ? "pro" : "soloQ";
    summary.push(
      `L'équipe ${teamLabel(strongerSide)} aligne des picks ${forceLabel} plus forts sur le patch ${patch} (${formatDeltaPoints(blueAvg - redAvg)} en moyenne).`,
    );
  } else if (isProMode && (blueAvg === null || redAvg === null)) {
    summary.push("Données pro insuffisantes pour comparer la force moyenne des deux équipes.");
  }

  const laneMatchups = generateLaneMatchups(result, isProMode);
  const decisiveMatchups = laneMatchups.filter((matchup) => Math.abs(matchup.deltaPoints) >= 4);
  if (decisiveMatchups.length > 0) {
    const top = decisiveMatchups[0];
    summary.push(top.summary);
  }

  const synergyGap = (result.blue.score_synergie - result.red.score_synergie) * 100;
  if (Math.abs(synergyGap) >= 2) {
    const side: "blue" | "red" = synergyGap > 0 ? "blue" : "red";
    summary.push(
      `L'affinité interne est meilleure côté ${teamLabel(side)} (${formatDeltaPoints(Math.abs(synergyGap) / 100)} sur le score ML de composition).`,
    );
  }

  const allAttributesBalanced = Object.keys(ATTRIBUTE_LABELS).every(
    (key) => Math.abs(result.differential[key as keyof typeof result.differential]) <= attributeThreshold,
  );
  const winratesBalanced = winrateGap <= winrateThreshold;

  if (allAttributesBalanced && winratesBalanced && summary.length === 0) {
    const mainFactor = dominantFactor(result);
    summary.push(`Draft très serrée : l'écart vient surtout de ${factorLabels[mainFactor]}.`);
  }

  if (summary.length === 0) {
    const forceLabel = isProMode ? "pro" : "soloQ";
    summary.push(
      `Les deux compositions restent proches : ni la force ${forceLabel} ni l'affinité ne créent un écart massif.`,
    );
  }

  return {
    summary: summary.slice(0, 4),
    blueAffinity: generateTeamAffinity(result.blue, "blue"),
    redAffinity: generateTeamAffinity(result.red, "red"),
    laneMatchups,
  };
}

export function translateMerakiRoleLabel(role: string): string {
  return translateMerakiRole(role);
}
