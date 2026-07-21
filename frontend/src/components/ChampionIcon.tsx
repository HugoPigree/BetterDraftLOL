import { getChampionIconUrl } from "../utils/ddragon";
import type { Role } from "../types/draft";

interface ChampionIconProps {
  championName?: string;
  version: string;
  size?: number;
  label?: string;
  className?: string;
  variant?: "default" | "ban" | "pick" | "pool";
  overlay?: "none" | "ban" | "picked";
  role?: Role;
  side?: "blue" | "red";
}

const ROLE_LABELS: Record<Role, string> = {
  TOP: "TOP",
  JUNGLE: "JG",
  MIDDLE: "MID",
  BOTTOM: "ADC",
  UTILITY: "SUP",
};

export function ChampionIcon({
  championName,
  version,
  size = 64,
  label,
  className = "",
  variant = "default",
  overlay = "none",
  role,
  side,
}: ChampionIconProps) {
  const isEmpty = !championName;

  return (
    <div
      className={[
        "champion-icon",
        `champion-icon--${variant}`,
        isEmpty ? "champion-icon--empty" : "",
        side ? `champion-icon--${side}` : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ width: size, height: size }}
      title={label ?? championName ?? "Slot vide"}
    >
      <div className="champion-icon__frame">
        {isEmpty ? (
          <div className="champion-icon__empty-slot">
            <span className="champion-icon__empty-mark" />
          </div>
        ) : (
          <img
            src={getChampionIconUrl(championName, version)}
            alt={championName}
            loading="lazy"
            className={overlay === "picked" ? "champion-icon__img--locked" : undefined}
            onError={(event) => {
              event.currentTarget.src = `https://ddragon.leagueoflegends.com/cdn/${version}/img/champion/Aatrox.png`;
            }}
          />
        )}

        {overlay === "ban" && !isEmpty && (
          <div className="champion-icon__overlay champion-icon__overlay--ban" aria-hidden="true">
            <span className="champion-icon__ban-slash" />
            <span className="champion-icon__ban-x">✕</span>
          </div>
        )}

        {overlay === "picked" && !isEmpty && (
          <div className="champion-icon__overlay champion-icon__overlay--picked" aria-hidden="true">
            <span className="champion-icon__picked-label">OUT</span>
          </div>
        )}

        {variant === "pick" && role && !isEmpty && (
          <span className={`champion-icon__role champion-icon__role--${role.toLowerCase()}`}>
            {ROLE_LABELS[role]}
          </span>
        )}
      </div>
    </div>
  );
}
