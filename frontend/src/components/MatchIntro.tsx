import { useState } from "react";
import type { BracketMatch, WorldsTeam } from "../types/worlds";
import { coachPortraitUrl } from "../utils/worldsCoachDialogue";
import { WorldsBrand } from "./WorldsBrand";

interface MatchIntroProps {
  match: BracketMatch;
  playerTeam: WorldsTeam;
  opponent: WorldsTeam;
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

export function MatchIntro({
  match,
  playerTeam,
  opponent,
  onBack,
  onStartDraft,
}: MatchIntroProps) {
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
