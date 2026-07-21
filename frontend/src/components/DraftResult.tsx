import { useEffect, useMemo, useState } from "react";
import type { DraftContext } from "../types/draft";
import type { PredictResponse } from "../types/predict";
import { normalizePredictResponse } from "../types/predict";
import { predictDraft } from "../services/api";
import { explainTeamScores, generateDraftAnalysis } from "../utils/generateAnalysis";
import { DraftResultDetails } from "./DraftResultDetails";

interface DraftResultProps {
  draft: DraftContext;
  patch: string;
  onReset: () => void;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function DraftResult({ draft, patch, onReset }: DraftResultProps) {
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!draft.isDraftComplete) {
      setResult(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    predictDraft(draft.bluePicks, draft.redPicks, patch)
      .then((prediction) => {
        if (!cancelled) {
          setResult(normalizePredictResponse(prediction));
        }
      })
      .catch((predictError: Error) => {
        if (!cancelled) {
          setError(predictError.message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [draft.isDraftComplete, draft.bluePicks, draft.redPicks, patch]);

  const analysisBundle = useMemo(
    () => (result ? generateDraftAnalysis(result, patch) : null),
    [result, patch],
  );

  return (
    <section className="draft-result">
      <div className="draft-result__header">
        <h2>Probabilité de victoire</h2>
        <span className="draft-result__patch">Patch {patch}</span>
      </div>

      {loading && (
        <div className="draft-result__loading">
          <span className="draft-result__spinner" />
          Calcul de la prédiction...
        </div>
      )}
      {error && <p className="error">{error}</p>}

      {result && analysisBundle && (
        <>
          <div className="draft-result__matchup">
            <TeamResultCard
              side="blue"
              label="Blue Side"
              probability={result.blue_win_probability}
              scores={result.blue}
            />
            <div className="draft-result__divider">VS</div>
            <TeamResultCard
              side="red"
              label="Red Side"
              probability={result.red_win_probability}
              scores={result.red}
            />
          </div>

          <DraftResultDetails result={result} analysisBundle={analysisBundle} />

          {result.warnings.length > 0 && (
            <div className="draft-result__warnings">
              <h3>Avertissements</h3>
              <ul>
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <button type="button" className="draft-result__reset" onClick={onReset}>
        Nouvelle draft
      </button>
    </section>
  );
}

function TeamResultCard({
  side,
  label,
  probability,
  scores,
}: {
  side: "blue" | "red";
  label: string;
  probability: number;
  scores: PredictResponse["blue"];
}) {
  const explanations = explainTeamScores(scores, side);

  return (
    <article className={`draft-result__card draft-result__card--${side}`}>
      <span className="draft-result__team-label">{label}</span>
      <strong className="draft-result__probability">{formatPercent(probability)}</strong>
      <div className="draft-result__meter">
        <div className="draft-result__meter-fill" style={{ width: `${probability * 100}%` }} />
      </div>
      <ul className="draft-result__stats">
        {explanations.map((entry) => (
          <li key={entry.label} className="draft-result__stat-row">
            <div className="draft-result__stat-head">
              <span>{entry.label}</span>
              <strong>{entry.value}</strong>
            </div>
            <p className="draft-result__stat-hint">{entry.hint}</p>
          </li>
        ))}
      </ul>
    </article>
  );
}
