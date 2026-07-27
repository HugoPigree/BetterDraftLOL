import type { LecScoutDossier, LecTeamIdentity } from "../types/lec";
import type { ScoutAction } from "../utils/lecScout";
import { familiarityLabel } from "../utils/lecScout";

interface LecScoutPanelProps {
  opponentName: string;
  identity: LecTeamIdentity;
  dossier: LecScoutDossier;
  discussLine: string | null;
  onDiscuss: (action: ScoutAction) => void;
}

export function LecScoutPanel({
  opponentName,
  identity,
  dossier,
  discussLine,
  onDiscuss,
}: LecScoutPanelProps) {
  return (
    <section className="lec-scout">
      <header className="lec-scout__header">
        <div>
          <p className="lec-hub__eyebrow">Scouting</p>
          <h3>Dossier — {opponentName}</h3>
          <p className="lec-scout__style">
            Style :{" "}
            <strong>{dossier.styleRevealed ? identity.label : "???"}</strong>
            {" · "}
            {familiarityLabel(dossier.familiarity)}
          </p>
        </div>
      </header>

      <div className="lec-scout__actions">
        <button
          type="button"
          className="worlds-btn worlds-btn--ghost"
          onClick={() => onDiscuss("style")}
        >
          Discuter — style de jeu
        </button>
        <button
          type="button"
          className="worlds-btn worlds-btn--ghost"
          disabled={dossier.revealedPicks.length >= 2}
          onClick={() => onDiscuss("picks")}
        >
          Discuter — picks favoris (1–2)
        </button>
      </div>

      {discussLine && <p className="lec-scout__line">{discussLine}</p>}

      {dossier.revealedPicks.length > 0 && (
        <ul className="lec-scout__hints">
          {dossier.revealedPicks.map((pick) => (
            <li key={`${pick.player}-${pick.champion}`}>
              {pick.player} ({pick.role}) — {pick.champion}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
