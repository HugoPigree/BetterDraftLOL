import {
  buildDeltaChips,
  formatDeltaChip,
  parseSuggestionReason,
} from "../utils/formatSuggestionReason";

interface SuggestionBreakdownProps {
  reason: string;
  gainPoints: number;
  deltaForce?: number;
  deltaSynergie?: number;
  deltaDuo?: number;
  compact?: boolean;
}

function formatGainBadge(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)} pt`;
}

export function SuggestionBreakdown({
  reason,
  gainPoints,
  deltaForce = 0,
  deltaSynergie = 0,
  deltaDuo = 0,
  compact = false,
}: SuggestionBreakdownProps) {
  const parsed = parseSuggestionReason(reason);
  const chips = buildDeltaChips(deltaForce, deltaSynergie, deltaDuo);
  const gainClass =
    gainPoints > 0
      ? "suggestion-breakdown__gain--positive"
      : gainPoints < 0
        ? "suggestion-breakdown__gain--negative"
        : "";

  return (
    <div className={`suggestion-breakdown${compact ? " suggestion-breakdown--compact" : ""}`}>
      <div className="suggestion-breakdown__headline-row">
        <p className="suggestion-breakdown__headline">{parsed.headline}</p>
        <span className={`suggestion-breakdown__gain ${gainClass}`}>
          {formatGainBadge(gainPoints)}
        </span>
      </div>

      {chips.length > 0 && (
        <ul className="suggestion-breakdown__chips" aria-label="Décomposition du gain">
          {chips.map((chip) => (
            <li
              key={chip.label}
              className={`suggestion-breakdown__chip ${
                chip.value >= 0
                  ? "suggestion-breakdown__chip--up"
                  : "suggestion-breakdown__chip--down"
              }`}
            >
              <span className="suggestion-breakdown__chip-label">{chip.label}</span>
              <span className="suggestion-breakdown__chip-value">
                {formatDeltaChip(chip.value)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {parsed.breakdown && (
        <p className="suggestion-breakdown__detail">{parsed.breakdown}</p>
      )}

      {parsed.warning && (
        <p className="suggestion-breakdown__warning" role="note">
          {parsed.warning}
        </p>
      )}

      {parsed.historical && (
        <p className="suggestion-breakdown__historical">
          {parsed.historical}{" "}
          <em className="suggestion-breakdown__disclaimer">(statistique historique moyenne)</em>
        </p>
      )}
    </div>
  );
}
