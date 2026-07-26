import { useState, type FormEvent } from "react";
import type { WorldsRoster } from "../types/worlds";
import { EMPTY_WORLDS_ROSTER, WORLDS_ROLES } from "../types/worlds";
import { WorldsBrand } from "./WorldsBrand";

interface WorldsSetupProps {
  loading: boolean;
  error: string | null;
  onBack: () => void;
  onStart: (teamName: string, coachName: string, roster: WorldsRoster) => void;
}

export function WorldsSetup({ loading, error, onBack, onStart }: WorldsSetupProps) {
  const [teamName, setTeamName] = useState("");
  const [coachName, setCoachName] = useState("");
  const [roster, setRoster] = useState<WorldsRoster>({ ...EMPTY_WORLDS_ROSTER });

  function updateRoster(role: keyof WorldsRoster, value: string) {
    setRoster((current) => ({ ...current, [role]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onStart(teamName.trim(), coachName.trim(), roster);
  }

  return (
    <div className="worlds-screen">
      <header className="worlds-screen__header worlds-screen__header--brand">
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={onBack}>
          Retour
        </button>
        <div className="worlds-screen__header-main">
          <WorldsBrand size="lg" subtitle="Créer ton équipe" />
        </div>
      </header>

      <form className="worlds-setup" onSubmit={handleSubmit}>
        <div className="worlds-setup__grid">
          <label className="worlds-field">
            <span>Nom de l&apos;équipe</span>
            <input
              value={teamName}
              onChange={(event) => setTeamName(event.target.value)}
              placeholder="Nom de ton équipe"
              autoComplete="off"
              required
            />
          </label>
          <label className="worlds-field">
            <span>Nom du coach</span>
            <input
              value={coachName}
              onChange={(event) => setCoachName(event.target.value)}
              placeholder="Nom du coach"
              autoComplete="off"
              required
            />
          </label>
        </div>

        <section className="worlds-setup__roster">
          <h2>Roster</h2>
          <div className="worlds-setup__roles">
            {WORLDS_ROLES.map((role) => (
              <label key={role} className="worlds-field">
                <span>{role}</span>
                <input
                  value={roster[role]}
                  onChange={(event) => updateRoster(role, event.target.value)}
                  placeholder={`Joueur ${role.toLowerCase()}`}
                  autoComplete="off"
                  required
                />
              </label>
            ))}
          </div>
        </section>

        {error && <p className="worlds-error">{error}</p>}

        <button type="submit" className="worlds-btn worlds-btn--primary" disabled={loading}>
          {loading ? "Préparation du bracket…" : "Lancer le tournoi"}
        </button>
      </form>
    </div>
  );
}
