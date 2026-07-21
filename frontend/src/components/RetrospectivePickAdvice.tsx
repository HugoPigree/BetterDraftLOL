import { useEffect, useMemo, useState } from "react";
import { suggestRetrospectivePick } from "../services/api";
import type { DraftContext, Role, Team } from "../types/draft";
import type { PredictionMode, RetrospectivePickSuggestion } from "../types/predict";
import {
  RETROSPECTIVE_PICK_METHODOLOGY,
  RETROSPECTIVE_PICK_METHODOLOGY_PRO,
} from "../copy/methodology";
import { getAvailableChampions } from "../utils/draftTeamBuilder";
import { AnalysisSection } from "./AnalysisSection";
import { ChampionIcon } from "./ChampionIcon";
import { MethodologyNote } from "./MethodologyNote";
import { SuggestionBreakdown } from "./SuggestionBreakdown";

const SIDE_LABELS: Record<Team, string> = {
  blue: "Blue Side",
  red: "Red Side",
};

const ROLE_ORDER: Role[] = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];

const ROLE_LABELS: Record<Role, string> = {
  TOP: "Top",
  JUNGLE: "Jungle",
  MIDDLE: "Mid",
  BOTTOM: "ADC",
  UTILITY: "Support",
};

function groupSuggestionsByRole(suggestions: RetrospectivePickSuggestion[]) {
  const groups = new Map<Role, RetrospectivePickSuggestion[]>();
  for (const item of suggestions) {
    const existing = groups.get(item.role) ?? [];
    existing.push(item);
    groups.set(item.role, existing);
  }

  return ROLE_ORDER.filter((role) => groups.has(role)).map((role) => ({
    role,
    currentChampion: groups.get(role)![0].current_champion,
    items: groups.get(role)!,
  }));
}

interface RetrospectivePickAdviceProps {
  draft: DraftContext;
  patch: string;
  predictionMode: PredictionMode;
  champions: string[];
  ddragonVersion: string;
  blueWinProbability: number;
  redWinProbability: number;
}

export function RetrospectivePickAdvice({
  draft,
  patch,
  predictionMode,
  champions,
  ddragonVersion,
  blueWinProbability,
  redWinProbability,
}: RetrospectivePickAdviceProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loserSide, setLoserSide] = useState<Team | null>(null);
  const [loserProbability, setLoserProbability] = useState<number | null>(null);
  const [suggestions, setSuggestions] = useState<RetrospectivePickSuggestion[]>([]);
  const [expandedRoles, setExpandedRoles] = useState<Set<Role>>(new Set());

  const loser = useMemo(() => {
    const diff = Math.abs(blueWinProbability - redWinProbability);
    if (diff < 0.02) {
      return null;
    }
    return blueWinProbability < redWinProbability
      ? { side: "blue" as Team, probability: blueWinProbability }
      : { side: "red" as Team, probability: redWinProbability };
  }, [blueWinProbability, redWinProbability]);

  useEffect(() => {
    if (!draft.isDraftComplete || !loser) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const available = getAvailableChampions(champions, draft.usedChampions);
    const teamPicks = loser.side === "blue" ? draft.bluePicks : draft.redPicks;
    const opponentPicks = loser.side === "blue" ? draft.redPicks : draft.bluePicks;

    suggestRetrospectivePick(loser.side, teamPicks, opponentPicks, patch, available, predictionMode)
      .then((result) => {
        if (!cancelled) {
          setLoserSide(loser.side);
          setLoserProbability(loser.probability);
          setSuggestions(result.suggestions);
          const roles = new Set(result.suggestions.map((item) => item.role));
          setExpandedRoles(roles);
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
    loser,
  ]);

  const suggestionsByRole = useMemo(
    () => groupSuggestionsByRole(suggestions),
    [suggestions],
  );

  if (!loser) {
    return null;
  }

  if (loading) {
    return (
      <AnalysisSection title="Picks manqués" className="retrospective-picks">
        <p className="analysis-section__loading">Analyse des meilleures réponses possibles…</p>
      </AnalysisSection>
    );
  }

  if (error || !loserSide || loserProbability === null || suggestions.length === 0) {
    return null;
  }

  const methodology =
    predictionMode === "pro" ? RETROSPECTIVE_PICK_METHODOLOGY_PRO : RETROSPECTIVE_PICK_METHODOLOGY;

  return (
    <AnalysisSection
      title="Picks manqués"
      subtitle={`${SIDE_LABELS[loserSide]} (${(loserProbability * 100).toFixed(1)} %) — jusqu'à 3 alternatives par rôle`}
      className={`retrospective-picks retrospective-picks--${loserSide}`}
    >
      <MethodologyNote variant="compact">
        <p>{methodology.body}</p>
      </MethodologyNote>

      <div className="retrospective-picks__roles">
        {suggestionsByRole.map(({ role, currentChampion, items }) => {
          const isOpen = expandedRoles.has(role);
          return (
            <details
              key={role}
              className="retrospective-picks__role-group"
              open={isOpen}
              onToggle={(event) => {
                const open = event.currentTarget.open;
                setExpandedRoles((prev) => {
                  const next = new Set(prev);
                  if (open) {
                    next.add(role);
                  } else {
                    next.delete(role);
                  }
                  return next;
                });
              }}
            >
              <summary className="retrospective-picks__role-summary">
                <span className="retrospective-picks__role-badge">{ROLE_LABELS[role]}</span>
                <span className="retrospective-picks__role-swap">
                  <ChampionIcon
                    championName={currentChampion}
                    version={ddragonVersion}
                    size={32}
                    side={loserSide}
                    role={role}
                  />
                  <span className="retrospective-picks__role-arrow">→</span>
                  <span className="retrospective-picks__alt-count">
                    {items.length} alternative{items.length > 1 ? "s" : ""}
                  </span>
                </span>
              </summary>

              <ol className="retrospective-picks__cards">
                {items.map((item, index) => (
                  <li
                    key={`${item.role}-${item.champion}`}
                    className="retrospective-picks__card"
                  >
                    <div className="retrospective-picks__card-hero">
                      <span className="retrospective-picks__rank">{index + 1}</span>
                      <ChampionIcon
                        championName={item.champion}
                        version={ddragonVersion}
                        size={48}
                        side={loserSide}
                        role={role}
                      />
                      <strong className="retrospective-picks__champion-name">{item.champion}</strong>
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
              </ol>
            </details>
          );
        })}
      </div>
    </AnalysisSection>
  );
}
