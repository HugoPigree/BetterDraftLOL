import type { DraftPick } from "../types/draft";
import type { LecDraftAnalysis } from "../utils/lecDraftAnalysis";

interface LecCareerDraftRecapProps {
  analysis: LecDraftAnalysis;
  playerTeamName: string;
  opponentTeamName: string;
  playerPicks: DraftPick[];
  opponentPicks: DraftPick[];
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
  playerPicks,
  opponentPicks,
  onPlayMatch,
  loading = false,
}: LecCareerDraftRecapProps) {
  return (
    <section className="lec-draft-recap">
      <header className="lec-draft-recap__header">
        <h3>Recap draft — meta carrière</h3>
        <p>Estimation basée sur les picks en vogue ce patch.</p>
      </header>

      <div className="lec-draft-recap__probability">
        <div className="lec-draft-recap__bar">
          <div
            className="lec-draft-recap__bar-fill"
            style={{ width: `${analysis.playerWinProbability * 100}%` }}
          />
        </div>
        <p>
          <strong>{playerTeamName}</strong> {formatPercent(analysis.playerWinProbability)}
          {" · "}
          <strong>{opponentTeamName}</strong> {formatPercent(1 - analysis.playerWinProbability)}
        </p>
      </div>

      <ul className="lec-draft-recap__highlights">
        {analysis.highlights.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>

      <div className="lec-draft-recap__comps">
        <article>
          <strong>{playerTeamName}</strong>
          <p>{playerPicks.map((pick) => pick.champion).join(" · ")}</p>
        </article>
        <article>
          <strong>{opponentTeamName}</strong>
          <p>{opponentPicks.map((pick) => pick.champion).join(" · ")}</p>
        </article>
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
