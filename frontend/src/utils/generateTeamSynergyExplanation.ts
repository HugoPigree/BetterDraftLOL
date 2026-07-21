import type { TeamSynergyInsight } from "../types/predict";

function formatMarginalPoints(points: number): string {
  const sign = points > 0 ? "+" : "";
  return `${sign}${points.toFixed(1)} pt`;
}

export function generateTeamSynergyExplanation(insight: TeamSynergyInsight): string {
  if (insight.explanation?.trim()) {
    return insight.explanation;
  }

  const { top_contributor, least_contributor } = insight;

  const topText = `${top_contributor.champion} contribue le plus à la synergie de cette équipe (${formatMarginalPoints(top_contributor.marginal_points)})`;

  if (least_contributor.champion === top_contributor.champion) {
    return `${topText}.`;
  }

  if (least_contributor.marginal_points < 0) {
    return (
      `${topText}, ${least_contributor.champion} affaiblit la synergie globale ` +
      `(${formatMarginalPoints(least_contributor.marginal_points)}).`
    );
  }

  const leastSuffix =
    least_contributor.marginal_points <= 0.05
      ? ", voire négatif"
      : "";

  return (
    `${topText}, ${least_contributor.champion} contribue le moins ` +
    `(${formatMarginalPoints(least_contributor.marginal_points)}${leastSuffix}).`
  );
}
