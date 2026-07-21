import { useEffect, useState } from "react";
import { suggestRetrospectiveBan } from "../services/api";
import type { DraftContext, Team } from "../types/draft";
import type { PredictionMode, RetrospectiveBanSuggestion } from "../types/predict";
import {
  RETROSPECTIVE_BAN_METHODOLOGY,
  RETROSPECTIVE_BAN_METHODOLOGY_PRO,
} from "../copy/methodology";
import { getAvailableChampions } from "../utils/draftTeamBuilder";
import { AnalysisSection } from "./AnalysisSection";
import { ChampionIcon } from "./ChampionIcon";
import { MethodologyNote } from "./MethodologyNote";
import { SuggestionBreakdown } from "./SuggestionBreakdown";

interface SideAdvice {
  side: Team;
  suggestions: RetrospectiveBanSuggestion[];
}

interface RetrospectiveBanAdviceProps {
  draft: DraftContext;
  patch: string;
  predictionMode: PredictionMode;
  champions: string[];
  ddragonVersion: string;
}

const SIDE_LABELS: Record<Team, string> = {
  blue: "Blue Side",
  red: "Red Side",
};

export function RetrospectiveBanAdvice({
  draft,
  patch,
  predictionMode,
  champions,
  ddragonVersion,
}: RetrospectiveBanAdviceProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [advice, setAdvice] = useState<SideAdvice[]>([]);

  useEffect(() => {
    if (!draft.isDraftComplete) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const available = getAvailableChampions(champions, draft.usedChampions);
    const sides: Team[] = ["blue", "red"];

    Promise.all(
      sides.map(async (side) => {
        const teamPicks = side === "blue" ? draft.bluePicks : draft.redPicks;
        const opponentPicks = side === "blue" ? draft.redPicks : draft.bluePicks;
        const result = await suggestRetrospectiveBan(
          side,
          teamPicks,
          opponentPicks,
          patch,
          available,
          predictionMode,
        );
        return { side, suggestions: result.suggestions };
      }),
    )
      .then((results) => {
        if (!cancelled) {
          setAdvice(results.filter((entry) => entry.suggestions.length > 0));
        }
      })
      .catch((fetchError: Error) => {
        if (!cancelled) {
          setError(fetchError.message);
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
  }, [
    draft.isDraftComplete,
    draft.bluePicks,
    draft.redPicks,
    draft.usedChampions,
    champions,
    patch,
    predictionMode,
  ]);

  if (loading) {
    return (
      <AnalysisSection title="Bans manqués" className="retrospective-bans">
        <p className="analysis-section__loading">Analyse des bans prioritaires…</p>
      </AnalysisSection>
    );
  }

  if (error || advice.length === 0) {
    return null;
  }

  const methodology =
    predictionMode === "pro" ? RETROSPECTIVE_BAN_METHODOLOGY_PRO : RETROSPECTIVE_BAN_METHODOLOGY;

  return (
    <AnalysisSection
      title="Bans manqués"
      subtitle="Picks adverses qui auraient mérité un ban"
      className="retrospective-bans"
    >
      <MethodologyNote variant="compact">
        <p>{methodology.body}</p>
      </MethodologyNote>

      {advice.map(({ side, suggestions }) => (
        <article key={side} className={`retrospective-bans__side retrospective-bans__side--${side}`}>
          <h4 className="retrospective-bans__side-title">{SIDE_LABELS[side]}</h4>
          <ul className="retrospective-bans__cards">
            {suggestions.map((item) => (
              <li key={item.champion} className="retrospective-bans__card">
                <div className="retrospective-bans__card-hero">
                  <ChampionIcon
                    championName={item.champion}
                    version={ddragonVersion}
                    size={48}
                    overlay="ban"
                  />
                  <div className="retrospective-bans__card-meta">
                    <strong>{item.champion}</strong>
                    <span className="retrospective-bans__replacement">
                      Remplacement probable : {item.replacement_champion}
                    </span>
                  </div>
                </div>
                <SuggestionBreakdown
                  reason={item.reason}
                  gainPoints={item.gain_percentage_points}
                  deltaForce={item.delta_force}
                  deltaSynergie={item.delta_synergie}
                  deltaDuo={item.delta_duo}
                />
              </li>
            ))}
          </ul>
        </article>
      ))}
    </AnalysisSection>
  );
}
