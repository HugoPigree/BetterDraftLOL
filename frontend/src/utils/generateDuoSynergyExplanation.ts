import type { DuoSynergyDetail } from "../types/predict";
import { INSUFFICIENT_DATA_LABEL } from "../types/predict";

export function explainDuoSynergyScore(
  duo: DuoSynergyDetail,
  label: string,
  isProMode = false,
): string {
  if (duo.insufficient_data || duo.score === null) {
    return `${label} : ${INSUFFICIENT_DATA_LABEL}`;
  }

  if (!duo.is_fallback && duo.games > 0) {
    return `${label} : winrate historique du duo en pro (${duo.games} games Oracle's Elixir avec cette paire exacte).`;
  }

  if (isProMode) {
    return `${label} : ${INSUFFICIENT_DATA_LABEL}`;
  }

  if (label.toLowerCase().includes("jungle")) {
    return `${label} : estimation Meraki (setup jungle + utilité/contrôle support) faute de games pro suffisantes.`;
  }

  return `${label} : estimation Meraki (dégâts adc + peel/support du duo bot) faute de games pro suffisantes.`;
}

export function explainDuoAdvantage(
  title: string,
  strongerSide: "blue" | "red" | "even",
  difference: number,
  insufficient = false,
  comparisonMessage?: string | null,
): string {
  if (insufficient && comparisonMessage) {
    return comparisonMessage;
  }

  if (insufficient) {
    return `${title} : ${INSUFFICIENT_DATA_LABEL}`;
  }

  if (strongerSide === "even") {
    return `${title} : les deux duos 2v2 sont estimés équilibrés (écart < 2 pt).`;
  }

  const side = strongerSide === "blue" ? "Blue" : "Red";
  const pts = (difference * 100).toFixed(1);
  return `${title} : ${side} Side avantagé d'environ ${pts} pt de winrate 2v2 dans le modèle global.`;
}
