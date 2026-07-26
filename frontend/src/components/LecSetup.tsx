import { useEffect, useState, type FormEvent } from "react";
import type { LecTeam } from "../types/lec";
import { EMPTY_LEC_ROSTER, LEC_ROLES } from "../types/lec";
import type { WorldsRoster } from "../types/worlds";
import { fetchLecTeams } from "../services/api";
import { LecBrand } from "./LecBrand";
import { LecTeamBadge } from "./LecTeamBadge";

interface LecSetupProps {
  loading: boolean;
  error: string | null;
  onBack: () => void;
  onStart: (
    teamName: string,
    coachName: string,
    roster: WorldsRoster,
    replaceTeamId: string,
  ) => void;
}

export function LecSetup({ loading, error, onBack, onStart }: LecSetupProps) {
  const [teamName, setTeamName] = useState("");
  const [coachName, setCoachName] = useState("");
  const [roster, setRoster] = useState<WorldsRoster>({ ...EMPTY_LEC_ROSTER });
  const [replaceTeamId, setReplaceTeamId] = useState("sk");
  const [lecTeams, setLecTeams] = useState<LecTeam[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchLecTeams()
      .then((response) => {
        if (!cancelled) {
          setLecTeams(response.teams);
        }
      })
      .catch((fetchError) => {
        if (!cancelled) {
          setCatalogError(
            fetchError instanceof Error
              ? fetchError.message
              : "Impossible de charger le catalogue LEC",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function updateRoster(role: keyof WorldsRoster, value: string) {
    setRoster((current) => ({ ...current, [role]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onStart(teamName.trim(), coachName.trim(), roster, replaceTeamId);
  }

  const replacedTeam = lecTeams.find((team) => team.id === replaceTeamId);

  return (
    <div className="worlds-screen">
      <header className="worlds-screen__header worlds-screen__header--brand">
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={onBack}>
          Retour
        </button>
        <div className="worlds-screen__header-main">
          <LecBrand size="lg" subtitle="Crée ton projet et entre en LEC" />
        </div>
      </header>

      <form className="worlds-setup lec-setup" onSubmit={handleSubmit}>
        <section className="lec-setup__intro">
          <p>
            Saison régulière <strong>Bo1</strong> — round-robin à 10 équipes. Top 6 playoffs (Bo3/Bo5).
            Top 3 <strong>qualifiés Worlds</strong>.
          </p>
        </section>

        <div className="worlds-setup__grid">
          <label className="worlds-field">
            <span>Nom de l&apos;équipe</span>
            <input
              value={teamName}
              onChange={(event) => setTeamName(event.target.value)}
              placeholder="Ex. Neon Dragons"
              autoComplete="off"
              required
            />
          </label>
          <label className="worlds-field">
            <span>Nom du coach</span>
            <input
              value={coachName}
              onChange={(event) => setCoachName(event.target.value)}
              placeholder="Ex. Arven"
              autoComplete="off"
              required
            />
          </label>
        </div>

        <section className="worlds-setup__roster">
          <h2>Roster</h2>
          <div className="worlds-setup__roles">
            {LEC_ROLES.map((role) => (
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

        <section className="lec-setup__replace">
          <h2>Remplace quelle équipe LEC ?</h2>
          <div className="lec-setup__team-grid">
            {lecTeams.map((team) => (
              <button
                key={team.id}
                type="button"
                className={[
                  "lec-setup__team-card",
                  replaceTeamId === team.id ? "lec-setup__team-card--active" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => setReplaceTeamId(team.id)}
              >
                <LecTeamBadge team={team} />
                <strong>{team.name}</strong>
                <span>Coach {team.coach}</span>
              </button>
            ))}
          </div>
          {replacedTeam && (
            <p className="lec-setup__replace-note">
              Tu prends la place de <strong>{replacedTeam.name}</strong> au calendrier officiel.
            </p>
          )}
        </section>

        {(error || catalogError) && <p className="worlds-error">{error ?? catalogError}</p>}

        <button type="submit" className="worlds-btn worlds-btn--primary" disabled={loading}>
          {loading ? "Préparation de la saison…" : "Commencer la carrière LEC"}
        </button>
      </form>
    </div>
  );
}
