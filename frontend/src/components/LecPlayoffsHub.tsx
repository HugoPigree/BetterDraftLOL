import type { BracketMatch } from "../types/worlds";
import type { LecTeam } from "../types/lec";
import { LecBrand } from "./LecBrand";
import { LecTeamBadge } from "./LecTeamBadge";

interface LecPlayoffsHubProps {
  bracket: BracketMatch[];
  playerTeam: LecTeam;
  onBack: () => void;
  onPlayNext: () => void;
}

export function LecPlayoffsHub({
  bracket,
  playerTeam,
  onBack,
  onPlayNext,
}: LecPlayoffsHubProps) {
  return (
    <div className="worlds-screen lec-hub lec-playoffs">
      <header className="worlds-screen__header">
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={onBack}>
          Saison
        </button>
        <LecBrand size="sm" subtitle="Playoffs LEC — Bo3 / Bo5" />
      </header>

      <div className="lec-playoffs__grid">
        {bracket.map((match) => {
          const teamA = match.team_a.team;
          const teamB = match.team_b.team;
          const isPlayerMatch =
            teamA?.id === playerTeam.id || teamB?.id === playerTeam.id;
          const resolved = Boolean(match.winner_id);

          return (
            <article
              key={match.id}
              className={[
                "lec-playoffs__match",
                isPlayerMatch ? "lec-playoffs__match--player" : "",
                resolved ? "lec-playoffs__match--done" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <p className="lec-playoffs__round">{match.round_label}</p>
              <div className="lec-playoffs__teams">
                <div className={match.winner_id === teamA?.id ? "lec-playoffs__winner" : ""}>
                  {teamA ? <LecTeamBadge team={teamA} active={teamA.id === playerTeam.id} /> : "TBD"}
                  <span>{teamA?.name ?? "À déterminer"}</span>
                </div>
                <span>vs</span>
                <div className={match.winner_id === teamB?.id ? "lec-playoffs__winner" : ""}>
                  {teamB ? <LecTeamBadge team={teamB} active={teamB.id === playerTeam.id} /> : "TBD"}
                  <span>{teamB?.name ?? "À déterminer"}</span>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      <button type="button" className="worlds-btn worlds-btn--primary" onClick={onPlayNext}>
        Jouer mon prochain match
      </button>
    </div>
  );
}
