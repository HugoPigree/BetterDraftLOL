import type { LecCareerProgress, LecUpgradeKey } from "../types/lec";
import { MAX_UPGRADE_LEVEL, UPGRADE_DETAILS } from "../utils/lecProgression";

interface LecProgressionPanelProps {
  progress: LecCareerProgress;
  onUpgrade: (key: LecUpgradeKey) => void;
}

export function LecProgressionPanel({ progress, onUpgrade }: LecProgressionPanelProps) {
  return (
    <section className="lec-progress">
      <div className="lec-progress__header">
        <h3>Progression carrière</h3>
        <span className="lec-progress__points">{progress.upgradePoints} point(s)</span>
      </div>

      {progress.weeklyEvent && (
        <div className="lec-progress__event">
          <strong>{progress.weeklyEvent.title}</strong>
          <p>{progress.weeklyEvent.description}</p>
        </div>
      )}

      {progress.winStreak >= 2 && (
        <p className="lec-progress__streak">Série : {progress.winStreak} victoires d&apos;affilée</p>
      )}

      <div className="lec-progress__upgrades">
        {(Object.keys(UPGRADE_DETAILS) as LecUpgradeKey[]).map((key) => {
          const detail = UPGRADE_DETAILS[key];
          const level = progress.upgrades[key];
          const canUpgrade =
            progress.upgradePoints > 0 && level < MAX_UPGRADE_LEVEL;
          return (
            <button
              key={key}
              type="button"
              className="lec-progress__upgrade"
              disabled={!canUpgrade}
              onClick={() => onUpgrade(key)}
            >
              <strong>{detail.label}</strong>
              <span>Lv. {level}/{MAX_UPGRADE_LEVEL}</span>
              <small>{detail.description}</small>
            </button>
          );
        })}
      </div>
    </section>
  );
}
