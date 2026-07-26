import { useEffect, useState } from "react";
import { useTypewriter } from "../hooks/useTypewriter";
import type { Team } from "../types/draft";
import type { WorldsTeam } from "../types/worlds";
import { coachPortraitUrl, regionAccentClass } from "../utils/worldsCoachDialogue";

interface WorldsCoachPanelProps {
  visible: boolean;
  line: string;
  botSide: Team;
  opponent: WorldsTeam;
}

export function WorldsCoachPanel({
  visible,
  line,
  botSide,
  opponent,
}: WorldsCoachPanelProps) {
  const { displayed, isComplete, skip } = useTypewriter(line, 22);
  const portrait = coachPortraitUrl(opponent);
  const [imageFailed, setImageFailed] = useState(false);
  const showPortrait = portrait && !imageFailed;

  useEffect(() => {
    setImageFailed(false);
  }, [opponent.id, portrait]);

  if (!visible || !line) {
    return null;
  }

  return (
    <div
      className={`bot-vn worlds-coach bot-vn--${botSide} ${regionAccentClass(opponent.region)}`}
      role="region"
      aria-label={`Coach ${opponent.coach}`}
    >
      <div className="bot-vn__stage">
        <div className="worlds-coach__sprite-wrap">
          {showPortrait ? (
            <img
              className="bot-vn__sprite worlds-coach__sprite"
              src={portrait}
              alt={`Coach ${opponent.coach}`}
              draggable={false}
              onError={() => setImageFailed(true)}
            />
          ) : (
            <div className="worlds-coach__sprite-fallback" aria-hidden="true">
              {opponent.coach.slice(0, 1).toUpperCase()}
            </div>
          )}
        </div>
        <div className="bot-vn__panel">
          <button type="button" className="bot-vn__box worlds-coach__box" onClick={skip}>
            <span className="bot-vn__name">
              Coach {opponent.coach} · {opponent.name}
            </span>
            <p className="bot-vn__text">
              {displayed}
              {!isComplete && <span className="bot-vn__cursor" aria-hidden="true" />}
            </p>
            {!isComplete && (
              <span className="bot-vn__hint">Cliquer pour accélérer</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
