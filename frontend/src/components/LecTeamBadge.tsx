import type { LecTeam } from "../types/lec";
import { lecTeamBadgeLabel, lecTeamColor } from "../utils/lecTeamBranding";

interface LecTeamBadgeProps {
  team: Pick<LecTeam, "short_name" | "name" | "brand_color">;
  size?: "sm" | "md" | "lg";
  active?: boolean;
}

export function LecTeamBadge({ team, size = "md", active = false }: LecTeamBadgeProps) {
  const label = lecTeamBadgeLabel(team);
  const color = lecTeamColor(team);

  return (
    <span
      className={[
        "lec-badge",
        `lec-badge--${size}`,
        active ? "lec-badge--active" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ "--lec-team-color": color } as React.CSSProperties}
      title={team.name}
    >
      {label}
    </span>
  );
}
