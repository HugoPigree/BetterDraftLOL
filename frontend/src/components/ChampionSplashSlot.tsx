import type { CSSProperties, KeyboardEvent, MouseEvent } from "react";
import type { DraftPick } from "../types/draft";
import { getChampionSplashUrl } from "../utils/ddragon";

interface ChampionSplashSlotProps {
  pick?: DraftPick;
  side: "blue" | "red";
  index: number;
  draggable?: boolean;
  showDragBadge?: boolean;
  editable?: boolean;
  selected?: boolean;
  highlighted?: boolean;
  dimmed?: boolean;
  onEdit?: () => void;
}

const ROLE_LABELS: Record<DraftPick["role"], string> = {
  TOP: "TOP",
  JUNGLE: "JG",
  MIDDLE: "MID",
  BOTTOM: "ADC",
  UTILITY: "SUP",
};

export function ChampionSplashSlot({
  pick,
  side,
  index,
  draggable = false,
  showDragBadge = false,
  editable = false,
  selected = false,
  highlighted = false,
  dimmed = false,
  onEdit,
}: ChampionSplashSlotProps) {
  const isEmpty = !pick;
  const isClickable = Boolean(editable && onEdit && !isEmpty);

  function handleActivate(event: MouseEvent | KeyboardEvent) {
    event.stopPropagation();
    onEdit?.();
  }

  return (
    <div
      className={[
        "splash-slot",
        `splash-slot--${side}`,
        isEmpty ? "splash-slot--empty" : "splash-slot--filled",
        draggable ? "splash-slot--draggable" : "",
        isClickable ? "splash-slot--editable" : "",
        selected ? "splash-slot--selected" : "",
        highlighted ? "splash-slot--highlighted" : "",
        dimmed ? "splash-slot--dimmed" : "",
      ].join(" ")}
      style={{ "--slot-index": index } as CSSProperties}
    >
      {showDragBadge && !isEmpty && (
        <span className="splash-slot__drag-badge" aria-hidden="true">
          DRAG
        </span>
      )}
      {isEmpty ? (
        <div className="splash-slot__placeholder">
          <svg className="splash-slot__helmet" viewBox="0 0 64 64" aria-hidden="true">
            <path
              d="M32 8c-12 0-20 8-22 18v6c0 2 1 4 3 5l2 14h34l2-14c2-1 3-3 3-5v-6C52 16 44 8 32 8zm0 6c6 0 10 4 12 10H20c2-6 6-10 12-10z"
              fill="currentColor"
              opacity="0.35"
            />
          </svg>
        </div>
      ) : (
        <div
          className="splash-slot__filled"
          key={pick.champion}
          role={isClickable ? "button" : undefined}
          tabIndex={isClickable ? 0 : undefined}
          aria-label={isClickable ? `Remplacer ${pick.champion}` : undefined}
          onClick={isClickable ? handleActivate : undefined}
          onKeyDown={
            isClickable
              ? (event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    handleActivate(event);
                  }
                }
              : undefined
          }
        >
          <img
            className="splash-slot__art"
            src={getChampionSplashUrl(pick.champion)}
            alt={pick.champion}
            loading="lazy"
          />
          <div className="splash-slot__shade" />
          <div className="splash-slot__info">
            <span className="splash-slot__name">{pick.champion.toUpperCase()}</span>
            <span className={`splash-slot__role splash-slot__role--${pick.role.toLowerCase()}`}>
              {ROLE_LABELS[pick.role]}
            </span>
          </div>
          {isClickable && (
            <span className="splash-slot__edit-hint">Cliquer pour remplacer</span>
          )}
        </div>
      )}
    </div>
  );
}
