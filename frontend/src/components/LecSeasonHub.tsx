import type { LecCareerProgress, LecFixture, LecSeasonState, LecTeam, LecUpgradeKey } from "../types/lec";
import { opponentForFixture } from "../utils/lecTeamBranding";
import { LecBrand } from "./LecBrand";
import { LecProgressionPanel } from "./LecProgressionPanel";
import { LecStandings } from "./LecStandings";
import { LecTeamBadge } from "./LecTeamBadge";

interface LecSeasonHubProps {
  season: LecSeasonState;
  playerTeam: LecTeam;
  progress: LecCareerProgress;
  onBack: () => void;
  onPlayNext: () => void;
  onUpgrade: (key: LecUpgradeKey) => void;
  onResetCareer: () => void;
}

function recentResults(season: LecSeasonState) {
  return season.fixtures
    .filter((fixture) => fixture.is_player_match && fixture.played)
    .slice(-3)
    .reverse();
}

function nextFixture(season: LecSeasonState): LecFixture | null {
  return (
    season.fixtures.find((fixture) => fixture.is_player_match && !fixture.played) ?? null
  );
}

export function LecSeasonHub({
  season,
  playerTeam,
  progress,
  onBack,
  onPlayNext,
  onUpgrade,
  onResetCareer,
}: LecSeasonHubProps) {
  const next = nextFixture(season);
  const opponent = next ? opponentForFixture(season.teams, next) : null;
  const playerRow = season.standings.find((row) => row.is_player_team);
  const playedCount = season.fixtures.filter(
    (fixture) => fixture.is_player_match && fixture.played,
  ).length;
  const recent = recentResults(season);

  function handleResetCareer() {
    if (
      window.confirm(
        "Recommencer une nouvelle carrière ?\n\nTa saison, ta progression et tes upgrades seront effacées.",
      )
    ) {
      onResetCareer();
    }
  }

  return (
    <div className="worlds-screen lec-hub">
      <header className="worlds-screen__header lec-hub__header">
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={onBack}>
          Accueil
        </button>
        <LecBrand size="sm" subtitle={season.season_label} />
        <button
          type="button"
          className="worlds-btn worlds-btn--ghost lec-hub__reset"
          onClick={handleResetCareer}
        >
          Nouvelle carrière
        </button>
      </header>

      <div className="lec-hub__layout">
        <section className="lec-hub__hero">
          <div className="lec-hub__team-card">
            <LecTeamBadge team={playerTeam} size="lg" active />
            <div>
              <h2>{playerTeam.name}</h2>
              <p>Coach {playerTeam.coach}</p>
              <p className="lec-hub__record">
                {playerRow ? (
                  <>
                    <strong>{playerRow.wins}V - {playerRow.losses}D</strong>
                    <span> · #{playerRow.rank} LEC</span>
                  </>
                ) : (
                  "Saison non commencée"
                )}
              </p>
            </div>
          </div>

          {next && opponent ? (
            <div className="lec-hub__next-match">
              <p className="lec-hub__eyebrow">{next.round_label}</p>
              <div className="lec-hub__matchup">
                <LecTeamBadge team={playerTeam} active />
                <span>vs</span>
                <LecTeamBadge team={opponent} />
                <strong>{opponent.name}</strong>
              </div>
              <p className="lec-hub__progress">
                Match {playedCount + 1}/9 · Semaine {next.week}
              </p>
              <button type="button" className="worlds-btn worlds-btn--primary" onClick={onPlayNext}>
                Préparer le match
              </button>
            </div>
          ) : (
            <div className="lec-hub__next-match">
              <p className="lec-hub__eyebrow">Phase régulière terminée</p>
              <button type="button" className="worlds-btn worlds-btn--primary" onClick={onPlayNext}>
                Voir la suite
              </button>
            </div>
          )}
        </section>

        <section className="lec-hub__side">
          <LecProgressionPanel progress={progress} onUpgrade={onUpgrade} />
          <h3>Classement LEC</h3>
          <LecStandings standings={season.standings} compact />
          {recent.length > 0 && (
            <div className="lec-hub__recent">
              <h3>Derniers résultats</h3>
              <ul>
                {recent.map((fixture) => {
                  const opp = opponentForFixture(season.teams, fixture);
                  const won = fixture.winner_id === playerTeam.id;
                  return (
                    <li key={fixture.id} className={won ? "lec-hub__recent--win" : "lec-hub__recent--loss"}>
                      {won ? "Victoire" : "Défaite"} vs {opp?.name ?? "?"}
                      <span>{fixture.round_label}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
