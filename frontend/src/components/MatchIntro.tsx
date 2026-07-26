import { useState } from "react";
import type { DraftPreferences, Team } from "../types/draft";
import type { BracketMatch, WorldsTeam } from "../types/worlds";
import { coachPortraitUrl } from "../utils/worldsCoachDialogue";
import { WorldsBrand } from "./WorldsBrand";

interface MatchIntroProps {
  match: BracketMatch;
  playerTeam: WorldsTeam;
  opponent: WorldsTeam;
  draftPreferences: DraftPreferences;
  onDraftPreferencesChange: (preferences: DraftPreferences) => void;
  onBack: () => void;
  onStartDraft: () => void;
}

function CoachPortrait({ team }: { team: WorldsTeam }) {
  const portrait = coachPortraitUrl(team);
  const [imageFailed, setImageFailed] = useState(false);
  const showPortrait = portrait && !imageFailed;

  return (
    <div className="match-intro__coach-portrait">
      {showPortrait ? (
        <img
          src={portrait}
          alt={`Coach ${team.coach}`}
          onError={() => setImageFailed(true)}
        />
      ) : (
        <div className="match-intro__coach-fallback">{team.coach.slice(0, 1)}</div>
      )}
    </div>
  );
}

function DraftPreferenceToggle<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string; className?: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="match-intro__pref-group">
      <span className="match-intro__pref-label">{label}</span>
      <div className="match-intro__pref-options">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            className={[
              "match-intro__pref-btn",
              option.className ?? "",
              value === option.value ? "match-intro__pref-btn--active" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function MatchIntro({
  match,
  playerTeam,
  opponent,
  draftPreferences,
  onDraftPreferencesChange,
  onBack,
  onStartDraft,
}: MatchIntroProps) {
  function updateSide(playerSide: Team) {
    onDraftPreferencesChange({ ...draftPreferences, playerSide });
  }

  function updatePickOrder(pickOrder: DraftPreferences["pickOrder"]) {
    onDraftPreferencesChange({ ...draftPreferences, pickOrder });
  }

  return (
    <div className="worlds-screen worlds-screen--center">
      <header className="worlds-screen__header">
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={onBack}>
          Bracket
        </button>
      </header>

      <div className="match-intro">
        <WorldsBrand size="md" subtitle={match.round_label} />

        <div className="match-intro__coach-row">
          <div className="match-intro__coach-card">
            <CoachPortrait team={playerTeam} />
            <strong>{playerTeam.name}</strong>
            <span>Coach {playerTeam.coach}</span>
          </div>
          <span className="match-intro__vs">VS</span>
          <div className="match-intro__coach-card match-intro__coach-card--opponent">
            <CoachPortrait team={opponent} />
            <strong>{opponent.name}</strong>
            <span>Coach {opponent.coach}</span>
          </div>
        </div>

        <section className="match-intro__draft-prefs">
          <h2>Configuration du match</h2>
          <DraftPreferenceToggle
            label="Côté"
            value={draftPreferences.playerSide}
            options={[
              { value: "blue", label: "Blue side", className: "match-intro__pref-btn--blue" },
              { value: "red", label: "Red side", className: "match-intro__pref-btn--red" },
            ]}
            onChange={updateSide}
          />
          <DraftPreferenceToggle
            label="Ordre de draft"
            value={draftPreferences.pickOrder}
            options={[
              { value: "first", label: "First pick" },
              { value: "last", label: "Last pick" },
            ]}
            onChange={updatePickOrder}
          />
        </section>

        <ul className="match-intro__roster">
          {(["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"] as const).map((role) => (
            <li key={role}>
              <span>{role}</span>
              <strong>{opponent.roster[role]}</strong>
            </li>
          ))}
        </ul>

        <p className="match-intro__hint">
          L&apos;adversaire draft avec ses picks signatures. Gagne la draft pour prendre l&apos;avantage
          en simulation.
        </p>

        <button type="button" className="worlds-btn worlds-btn--primary" onClick={onStartDraft}>
          Commencer la draft
        </button>
      </div>
    </div>
  );
}
