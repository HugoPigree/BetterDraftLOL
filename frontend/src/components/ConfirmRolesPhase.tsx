import type { DraftPick, Role, Team } from "../types/draft";
import type { RoleValidation } from "../utils/autoAssignRoles";
import { getMerakiMismatchWarnings } from "../utils/autoAssignRoles";

interface ConfirmRolesPhaseProps {
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  blueConfirmed: boolean;
  redConfirmed: boolean;
  blueValidation: RoleValidation;
  redValidation: RoleValidation;
  championPositions: Record<string, Role[]>;
  onConfirmTeam: (side: Team) => void;
}

function TeamConfirmPanel({
  side,
  label,
  confirmed,
  validation,
  picks,
  championPositions,
  onConfirm,
}: {
  side: Team;
  label: string;
  confirmed: boolean;
  validation: RoleValidation;
  picks: DraftPick[];
  championPositions: Record<string, Role[]>;
  onConfirm: () => void;
}) {
  const merakiWarnings = getMerakiMismatchWarnings(picks, championPositions);

  return (
    <article className={`confirm-roles__team confirm-roles__team--${side}`}>
      <header className="confirm-roles__team-head">
        <h3>{label}</h3>
        {confirmed && <span className="confirm-roles__badge confirm-roles__badge--done">Confirmé</span>}
      </header>

      {!validation.valid && validation.message && (
        <p className="confirm-roles__error" role="alert">
          {validation.message}
        </p>
      )}

      {validation.valid && merakiWarnings.length > 0 && (
        <ul className="confirm-roles__warnings">
          {merakiWarnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <button
        type="button"
        className={[
          "confirm-roles__confirm-btn",
          `confirm-roles__confirm-btn--${side}`,
          confirmed ? "confirm-roles__confirm-btn--done" : "",
        ].join(" ")}
        disabled={!validation.valid || confirmed}
        onClick={onConfirm}
      >
        {confirmed ? "Rôles confirmés" : "Confirm roles"}
      </button>
    </article>
  );
}

export function ConfirmRolesPhase({
  bluePicks,
  redPicks,
  blueConfirmed,
  redConfirmed,
  blueValidation,
  redValidation,
  championPositions,
  onConfirmTeam,
}: ConfirmRolesPhaseProps) {
  const bothConfirmed = blueConfirmed && redConfirmed;

  return (
    <section className="confirm-roles">
      <header className="confirm-roles__header">
        <h2>Assignation des rôles</h2>
        <p>
          Glissez les champions dans les slots latéraux pour ajuster TOP → SUPPORT. Les rôles sont
          pré-remplis via Meraki ; confirmez chaque équipe avant l&apos;analyse.
        </p>
      </header>

      <div className="confirm-roles__teams">
        <TeamConfirmPanel
          side="blue"
          label="Blue Side"
          confirmed={blueConfirmed}
          validation={blueValidation}
          picks={bluePicks}
          championPositions={championPositions}
          onConfirm={() => onConfirmTeam("blue")}
        />
        <TeamConfirmPanel
          side="red"
          label="Red Side"
          confirmed={redConfirmed}
          validation={redValidation}
          picks={redPicks}
          championPositions={championPositions}
          onConfirm={() => onConfirmTeam("red")}
        />
      </div>

      <p className="confirm-roles__hint">
        {bothConfirmed
          ? "Les deux équipes sont confirmées — lancement de la prédiction…"
          : "Confirmez Blue Side et Red Side pour lancer l'analyse."}
      </p>
    </section>
  );
}
