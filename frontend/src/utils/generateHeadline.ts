import type { PredictResponse, PredictionMode } from "../types/predict";

function favoriteSide(result: PredictResponse): "blue" | "red" | "even" {
  const diff = Math.abs(result.blue_win_probability - result.red_win_probability) * 100;
  if (diff < 2) {
    return "even";
  }
  return result.blue_win_probability > result.red_win_probability ? "blue" : "red";
}

function sideLabel(side: "blue" | "red"): string {
  return side === "blue" ? "Blue" : "Red";
}

export function generateVictoryHeadline(
  result: PredictResponse,
  mode: PredictionMode = "mixed",
): string {
  const favorite = favoriteSide(result);
  const diffPoints = Math.abs(result.blue_win_probability - result.red_win_probability) * 100;

  if (favorite === "even") {
    return "Les deux équipes sont très proches (50/50), aucun facteur ne se démarque nettement.";
  }

  const favoriteProb = Math.round(
    Math.max(result.blue_win_probability, result.red_win_probability) * 100,
  );
  const intensity =
    diffPoints < 4 ? "légèrement" : diffPoints < 8 ? "modérément" : "clairement";

  const reasons: string[] = [];
  const blueForce = result.blue.score_force;
  const redForce = result.red.score_force;
  const forceDiff =
    blueForce !== null && redForce !== null ? (blueForce - redForce) * 100 : 0;
  const synergyDiff = (result.blue.score_synergie - result.red.score_synergie) * 100;

  if (Math.abs(forceDiff) >= 1.5) {
    reasons.push(
      mode === "pro"
        ? "ses champions sont plus performants en pro sur les patchs disponibles"
        : "ses champions sont plus performants sur le patch actuel",
    );
  }
  if (Math.abs(synergyDiff) >= 1.5) {
    reasons.push("une meilleure synergie de composition");
  }

  const duoDiff = result.duo_differential;
  if (duoDiff) {
    if (
      duoDiff.jungle_support_advantage.stronger_side === favorite &&
      duoDiff.jungle_support_advantage.difference >= 0.02
    ) {
      reasons.push("un avantage de matchup jungle-support 2v2");
    }
    if (
      duoDiff.bot_lane_advantage.stronger_side === favorite &&
      duoDiff.bot_lane_advantage.difference >= 0.02
    ) {
      reasons.push("un avantage de matchup bot lane 2v2");
    }
  }

  const reasonText =
    reasons.length > 0
      ? `, principalement grâce à ${reasons.slice(0, 2).join(" et ")}`
      : diffPoints < 4
        ? ", sur un avantage très fin"
        : "";

  return `L'équipe ${sideLabel(favorite)} est ${intensity} favorite (${favoriteProb}%)${reasonText}.`;
}
