/** Met en forme les textes de justification longs pour un affichage lisible. */

const HISTORICAL_DISCLAIMER = "(statistique historique moyenne)";

export interface ParsedSuggestionReason {
  headline: string;
  breakdown: string | null;
  warning: string | null;
  historical: string | null;
}

export function parseSuggestionReason(reason: string): ParsedSuggestionReason {
  let text = reason.trim();
  let warning: string | null = null;
  let historical: string | null = null;

  const warningIndex = text.indexOf("Attention :");
  if (warningIndex >= 0) {
    warning = text.slice(warningIndex).replace(/\.\s*$/, "").trim();
    text = text.slice(0, warningIndex).trim().replace(/\.\s*$/, "");
  }

  const histIndex = text.indexOf(HISTORICAL_DISCLAIMER);
  if (histIndex >= 0) {
    const beforeHist = text.slice(0, histIndex).trim().replace(/\.\s*$/, "");
    const sentences = beforeHist.split(/(?<=\.)\s+/);
    historical = sentences.pop()?.trim() || null;
    text = sentences.join(" ").trim();
  }

  const splitIndex = text.indexOf(" — dont ");
  if (splitIndex >= 0) {
    return {
      headline: text.slice(0, splitIndex).trim(),
      breakdown: text.slice(splitIndex + 3).trim(),
      warning,
      historical,
    };
  }

  return {
    headline: text,
    breakdown: null,
    warning,
    historical,
  };
}

export interface DeltaChip {
  label: string;
  value: number;
}

export function buildDeltaChips(
  deltaForce: number,
  deltaSynergie: number,
  deltaDuo: number,
): DeltaChip[] {
  const chips: DeltaChip[] = [
    { label: "Lane / force", value: deltaForce },
    { label: "Synergie compo", value: deltaSynergie },
  ];
  if (Math.abs(deltaDuo) >= 0.05) {
    chips.push({ label: "Duos 2v2", value: deltaDuo });
  }
  return chips.filter((chip) => Math.abs(chip.value) >= 0.05);
}

export function formatDeltaChip(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)} pt`;
}
