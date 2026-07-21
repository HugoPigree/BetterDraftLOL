import { useEffect, useMemo, useState } from "react";
import type { Role, Team } from "../types/draft";
import type { PredictionMode, RetrospectivePickSuggestion } from "../types/predict";
import {
  RETROSPECTIVE_PICK_METHODOLOGY,
  RETROSPECTIVE_PICK_METHODOLOGY_PRO,
} from "../copy/methodology";
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
  loading: boolean;
  error: string | null;
  loserSide: Team;
  loserProbability: number;
  suggestions: RetrospectivePickSuggestion[];
  predictionMode: PredictionMode;
  ddragonVersion: string;
}

export function RetrospectivePickAdvice({
  loading,
  error,
  loserSide,
  loserProbability,
  suggestions,
  predictionMode,
  ddragonVersion,
}: RetrospectivePickAdviceProps) {
  const [expandedRoles, setExpandedRoles] = useState<Set<Role>>(new Set());

  useEffect(() => {
    if (suggestions.length > 0) {
      setExpandedRoles(new Set(suggestions.map((item) => item.role)));
    }
  }, [suggestions]);

  const suggestionsByRole = useMemo(
    () => groupSuggestionsByRole(suggestions),
    [suggestions],
  );

  const methodology =
    predictionMode === "pro" ? RETROSPECTIVE_PICK_METHODOLOGY_PRO : RETROSPECTIVE_PICK_METHODOLOGY;

  if (loading) {
    return (
      <AnalysisSection title="Picks manqués" className="retrospective-picks">
        <p className="analysis-section__loading">
          Analyse des meilleures réponses possibles… (10–20 s)
        </p>
      </AnalysisSection>
    );
  }

  if (error) {
    return (
      <AnalysisSection title="Picks manqués" className="retrospective-picks">
        <p className="analysis-section__error" role="alert">
          {error}
        </p>
      </AnalysisSection>
    );
  }

  if (suggestions.length === 0) {
    return (
      <AnalysisSection title="Picks manqués" className="retrospective-picks">
        <p className="analysis-section__empty">
          Aucune alternative trouvée pour {SIDE_LABELS[loserSide]} sur cette draft.
        </p>
      </AnalysisSection>
    );
  }

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
