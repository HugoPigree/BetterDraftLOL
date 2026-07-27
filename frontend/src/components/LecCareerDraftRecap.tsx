import type { LecDraftAnalysis } from "../utils/lecDraftAnalysis";

interface LecCareerDraftRecapProps {
  analysis: LecDraftAnalysis;
  playerTeamName: string;
  opponentTeamName: string;
  onPlayMatch: () => void;
  loading?: boolean;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function LecCareerDraftRecap({
  analysis,
  playerTeamName,
  opponentTeamName,
  onPlayMatch,
  loading = false,
}: LecCareerDraftRecapProps) {
  return (
    <section className="lec-draft-recap">
      <div className="lec-draft-recap__probability">
        <div className="lec-draft-recap__bar">
          <div
            className="lec-draft-recap__bar-fill"
            style={{ width: `${analysis.playerWinProbability * 100}%` }}
          />
        </div>
        <p className="lec-draft-recap__scores">
          <strong>{playerTeamName}</strong> {formatPercent(analysis.playerWinProbability)}
          {" · "}
          <strong>{opponentTeamName}</strong> {formatPercent(1 - analysis.playerWinProbability)}
        </p>
      </div>

      <button
        type="button"
        className="worlds-btn worlds-btn--primary lec-draft-recap__cta"
        disabled={loading}
        onClick={onPlayMatch}
      >
        {loading ? "Résultat en cours…" : "Jouer le match"}
      </button>
    </section>
  );
}
