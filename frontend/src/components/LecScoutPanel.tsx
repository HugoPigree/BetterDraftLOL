import type { LecScoutDossier, LecTeamIdentity } from "../types/lec";
import { familiarityLabel } from "../utils/lecScout";

interface LecScoutPanelProps {
  opponentName: string;
  identity: LecTeamIdentity;
  dossier: LecScoutDossier;
  discussLine: string | null;
  onDiscuss: (questionIndex: number) => void;
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
            Style repéré : <strong>{identity.label}</strong> · {familiarityLabel(dossier.familiarity)}
          </p>
        </div>
      </header>

      <div className="lec-scout__actions">
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={() => onDiscuss(0)}>
          Discuter — tempo
        </button>
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={() => onDiscuss(1)}>
          Discuter — carry
        </button>
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={() => onDiscuss(2)}>
          Discuter — bans
        </button>
      </div>

      {discussLine && <p className="lec-scout__line">{discussLine}</p>}

      {dossier.hints.length > 0 && (
        <ul className="lec-scout__hints">
          {dossier.hints.map((hint) => (
            <li key={hint}>{hint}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
