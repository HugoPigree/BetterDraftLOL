import type { Team } from "../types/draft";

/** Équipe avec la probabilité la plus basse (suggestions rétrospectives, chatbot). */
export function resolveLoserSide(blueProb: number, redProb: number): Team {
  return blueProb <= redProb ? "blue" : "red";
}

export function resolveLoserProbability(blueProb: number, redProb: number, side: Team): number {
  return side === "blue" ? blueProb : redProb;
}
