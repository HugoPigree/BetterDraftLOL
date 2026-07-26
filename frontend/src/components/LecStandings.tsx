import type { LecStandingRow } from "../types/lec";
import { LecTeamBadge } from "./LecTeamBadge";

interface LecStandingsProps {
  standings: LecStandingRow[];
  compact?: boolean;
}

export function LecStandings({ standings, compact = false }: LecStandingsProps) {
  return (
    <div className={`lec-standings${compact ? " lec-standings--compact" : ""}`}>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Équipe</th>
            <th>V</th>
            <th>D</th>
            {!compact && <th>Win%</th>}
          </tr>
        </thead>
        <tbody>
          {standings.map((row) => (
            <tr
              key={row.team_id}
              className={[
                row.is_player_team ? "lec-standings__row--player" : "",
                row.playoffs_cutoff ? "lec-standings__row--playoffs" : "",
                row.worlds_cutoff ? "lec-standings__row--worlds" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <td>{row.rank}</td>
              <td>
                <span className="lec-standings__team">
                  <LecTeamBadge
                    team={{
                      name: row.team_name,
                      short_name: row.short_name,
                      brand_color: row.brand_color,
                    }}
                    size="sm"
                    active={row.is_player_team}
                  />
                  <span>{row.team_name}</span>
                </span>
              </td>
              <td>{row.wins}</td>
              <td>{row.losses}</td>
              {!compact && <td>{Math.round(row.win_rate * 100)}%</td>}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="lec-standings__legend">
        Top 6 playoffs · Top 3 Worlds
      </p>
    </div>
  );
}
