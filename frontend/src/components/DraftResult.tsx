import { useEffect, useMemo, useState } from "react";
import type { DraftContext, DraftPick } from "../types/draft";
import type { PredictResponse, PredictionMode } from "../types/predict";
import { normalizePredictResponse } from "../types/predict";
import {
  PREDICT_METHODOLOGY,
  PREDICT_METHODOLOGY_PRO,
  HEADLINE_METHODOLOGY,
  HEADLINE_METHODOLOGY_PRO,
} from "../copy/methodology";
import { predictDraft } from "../services/api";
import { explainTeamScores, generateDraftAnalysis } from "../utils/generateAnalysis";
import { generateVictoryHeadline } from "../utils/generateHeadline";
import { DraftResultDetails } from "./DraftResultDetails";
import { DuoSynergiesSection } from "./DuoSynergiesSection";
import { MethodologyNote } from "./MethodologyNote";
import { RetrospectiveBanAdvice } from "./RetrospectiveBanAdvice";
import { RetrospectivePickAdvice } from "./RetrospectivePickAdvice";
import { DraftChatbot } from "./DraftChatbot";
import { useRetrospectiveAdvice } from "../hooks/useRetrospectiveAdvice";

interface DraftResultProps {
  draft: DraftContext;
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  patch: string;
  predictionMode: PredictionMode;
  ddragonVersion: string;
  champions: string[];
  usedChampions: string[];
  onReset: () => void;
  onStartEditing: () => void;
  isEditing?: boolean;
  botEnabled?: boolean;
  onExplainBotChoices?: () => void;
  explainLoading?: boolean;
  explainError?: string | null;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function DraftResult({
  draft,
  bluePicks,
  redPicks,
  patch,
  predictionMode,
  ddragonVersion,
  champions,
  usedChampions,
  onReset,
  onStartEditing,
  isEditing = false,
  botEnabled = false,
  onExplainBotChoices,
  explainLoading = false,
  explainError = null,
}: DraftResultProps) {
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);

    predictDraft(bluePicks, redPicks, patch, predictionMode)
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
  }, [bluePicks, redPicks, patch, predictionMode]);

  const isProMode = predictionMode === "pro";
  const methodology = isProMode ? PREDICT_METHODOLOGY_PRO : PREDICT_METHODOLOGY;
  const headlineMethodology = isProMode ? HEADLINE_METHODOLOGY_PRO : HEADLINE_METHODOLOGY;

  const analysisBundle = useMemo(
    () => (result ? generateDraftAnalysis(result, patch, predictionMode) : null),
    [result, patch, predictionMode],
  );

  const headline = useMemo(
    () => (result ? generateVictoryHeadline(result, predictionMode) : null),
    [result, predictionMode],
  );

  const resultDraft = useMemo(
    (): DraftContext => ({
      ...draft,
      bluePicks,
      redPicks,
    }),
    [draft, bluePicks, redPicks],
  );

  const retrospectiveAdvice = useRetrospectiveAdvice(
    Boolean(result),
    bluePicks,
    redPicks,
    result?.blue_win_probability ?? 0.5,
    result?.red_win_probability ?? 0.5,
    patch,
    predictionMode,
    champions,
    usedChampions,
  );

  return (
    <section className="draft-result">
      <div className="draft-result__header">
        <h2>Probabilité de victoire</h2>
        <span className="draft-result__patch">Patch {patch}</span>
      </div>

      <MethodologyNote
        title={methodology.title}
        disclaimer={methodology.disclaimer}
        variant="compact"
      >
        <p>{methodology.body}</p>
      </MethodologyNote>

      {loading && (
        <div className="draft-result__loading">
          <span className="draft-result__spinner" />
          Calcul de la prédiction...
        </div>
      )}
      {error && <p className="error">{error}</p>}

      {result && analysisBundle && headline && (
        <>
          <div className="draft-result__headline-block">
            <p className="draft-result__headline">{headline}</p>
            <p className="draft-result__headline-note">{headlineMethodology.disclaimer}</p>
          </div>

          <div className="draft-result__matchup">
            <TeamResultCard
              side="blue"
              label="Blue Side"
              probability={result.blue_win_probability}
              scores={result.blue}
              isProMode={isProMode}
            />
            <div className="draft-result__divider">VS</div>
            <TeamResultCard
              side="red"
              label="Red Side"
              probability={result.red_win_probability}
              scores={result.red}
              isProMode={isProMode}
            />
          </div>

          {result.duo_synergies &&
            result.duo_differential &&
            result.bot_lane_matchup &&
            result.jungle_support_matchup && (
              <DuoSynergiesSection
                blueTeam={result.blue}
                redTeam={result.red}
                duoSynergies={result.duo_synergies}
                botLaneMatchup={result.bot_lane_matchup}
                jungleSupportMatchup={result.jungle_support_matchup}
                duoDifferential={result.duo_differential}
                ddragonVersion={ddragonVersion}
                isProMode={isProMode}
              />
            )}

          <DraftResultDetails result={result} analysisBundle={analysisBundle} isProMode={isProMode} />

          <div className="draft-result__insights">
            <RetrospectiveBanAdvice
              draft={resultDraft}
              patch={patch}
              predictionMode={predictionMode}
              champions={champions}
              ddragonVersion={ddragonVersion}
            />

            <RetrospectivePickAdvice
              loading={retrospectiveAdvice.loading}
              error={retrospectiveAdvice.error}
              loserSide={retrospectiveAdvice.loserSide}
              loserProbability={retrospectiveAdvice.loserProbability}
              suggestions={retrospectiveAdvice.pickSuggestions}
              predictionMode={predictionMode}
              ddragonVersion={ddragonVersion}
            />

            <DraftChatbot
              result={result}
              bluePicks={bluePicks}
              redPicks={redPicks}
              patch={patch}
              predictionMode={predictionMode}
              champions={champions}
              usedChampions={usedChampions}
              blueWinProbability={result.blue_win_probability}
              redWinProbability={result.red_win_probability}
              retrospectivePicks={retrospectiveAdvice.pickSuggestions}
              retrospectiveBans={retrospectiveAdvice.banSuggestions}
            />
          </div>

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

      <div className="draft-result__footer-actions">
        {!isEditing && (
          <button type="button" className="draft-result__edit" onClick={onStartEditing}>
            Modifier la compo
          </button>
        )}
        {botEnabled && !isEditing && onExplainBotChoices && (
          <button
            type="button"
            className="draft-result__edit draft-result__explain"
            onClick={onExplainBotChoices}
            disabled={explainLoading}
          >
            {explainLoading ? "Chargement…" : "Explication des choix"}
          </button>
        )}
        <button type="button" className="draft-result__reset" onClick={onReset}>
          Nouvelle draft
        </button>
      </div>
      {explainError && <p className="error">{explainError}</p>}
    </section>
  );
}

function TeamResultCard({
  side,
  label,
  probability,
  scores,
  isProMode,
}: {
  side: "blue" | "red";
  label: string;
  probability: number;
  scores: PredictResponse["blue"];
  isProMode: boolean;
}) {
  const explanations = explainTeamScores(scores, side, isProMode);

  return (
    <article className={`draft-result__card draft-result__card--${side}`}>
      <span className="draft-result__team-label">{label}</span>
      <strong className="draft-result__probability">{formatPercent(probability)}</strong>
      <div className="draft-result__meter">
        <div className="draft-result__meter-fill" style={{ width: `${probability * 100}%` }} />
      </div>

      <details className="draft-result__details-toggle">
        <summary>Voir le détail du calcul</summary>
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
      </details>
    </article>
  );
}
