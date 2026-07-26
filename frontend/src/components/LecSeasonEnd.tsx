import type { LecStandingRow } from "../types/lec";
import { LecBrand } from "./LecBrand";
import { LecStandings } from "./LecStandings";

interface LecSeasonEndProps {
  playerRow: LecStandingRow | null;
  worldsQualified: boolean;
  onRestart: () => void;
  onBackHome: () => void;
}

export function LecSeasonEnd({
  playerRow,
  worldsQualified,
  onRestart,
  onBackHome,
}: LecSeasonEndProps) {
  return (
    <div className="worlds-screen worlds-screen--center lec-season-end">
      <LecBrand
        size="md"
        subtitle={worldsQualified ? "Qualifié pour Worlds" : "Fin de saison LEC"}
      />

      <div className={`lec-season-end__banner${worldsQualified ? " lec-season-end__banner--worlds" : ""}`}>
        {worldsQualified ? (
          <>
            <h2>Ticket Worlds obtenu</h2>
            <p>
              Top 3 LEC confirmé. Tu représenteras l&apos;EMEA sur la scène internationale.
            </p>
          </>
        ) : (
          <>
            <h2>Saison terminée</h2>
            <p>
              Classement final #{playerRow?.rank ?? "?"} — la route vers Worlds passera par une
              nouvelle saison.
            </p>
          </>
        )}
      </div>

      {playerRow && (
        <p className="lec-season-end__record">
          Bilan : <strong>{playerRow.wins}V - {playerRow.losses}D</strong>
        </p>
      )}

      <div className="lec-season-end__actions">
        <button type="button" className="worlds-btn worlds-btn--primary" onClick={onRestart}>
          Nouvelle carrière
        </button>
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={onBackHome}>
          Retour à l&apos;accueil
        </button>
      </div>
    </div>
  );
}

interface LecWorldsQualifiedProps {
  playerTeamName: string;
  onContinue: () => void;
}

export function LecWorldsQualified({ playerTeamName, onContinue }: LecWorldsQualifiedProps) {
  return (
    <div className="worlds-screen worlds-screen--center lec-season-end">
      <LecBrand size="lg" subtitle="EMEA représentée" />
      <div className="lec-season-end__banner lec-season-end__banner--worlds">
        <h2>{playerTeamName} aux Worlds</h2>
        <p>
          Troisième pilier du classement LEC. La draft et la simulation t&apos;ont mené jusqu&apos;ici —
          la suite se joue sur la scène mondiale.
        </p>
      </div>
      <button type="button" className="worlds-btn worlds-btn--primary" onClick={onContinue}>
        Voir le bilan de saison
      </button>
    </div>
  );
}

export function LecSeasonEndWithStandings({
  standings,
  ...props
}: LecSeasonEndProps & { standings: LecStandingRow[] }) {
  return (
    <div className="worlds-screen lec-season-end-screen">
      <LecSeasonEnd {...props} />
      <section className="lec-season-end__standings">
        <h3>Classement final</h3>
        <LecStandings standings={standings} />
      </section>
    </div>
  );
}
