import { useEffect, useMemo, useState } from "react";
import { ChampionIcon } from "./ChampionIcon";
import { TeamSynergySection } from "./TeamSynergyCard";
import type {
  DuoAdvantage,
  DuoMatchupDetail,
  DuoSynergyDetail,
  SideDuoSynergies,
  TeamPredictionDetail,
} from "../types/predict";
import {
  generateMatchupExplanation,
  type MatchupExplanation,
} from "../utils/generateMatchupExplanation";
import {
  explainDuoAdvantage,
  explainDuoSynergyScore,
} from "../utils/generateDuoSynergyExplanation";
import { loadMerakiChampionCatalog, type MerakiChampionCatalog } from "../utils/merakiFeatures";
import { DUO_ADVANTAGE_METHODOLOGY, DUO_SECTION_METHODOLOGY, DUO_SECTION_METHODOLOGY_PRO } from "../copy/methodology";
import { INSUFFICIENT_DATA_LABEL } from "../types/predict";
import { MethodologyNote } from "./MethodologyNote";

interface DuoSynergiesSectionProps {
  blueTeam: TeamPredictionDetail;
  redTeam: TeamPredictionDetail;
  duoSynergies: SideDuoSynergies;
  botLaneMatchup: DuoMatchupDetail;
  jungleSupportMatchup: DuoMatchupDetail;
  duoDifferential: {
    jungle_support_advantage: DuoAdvantage;
    bot_lane_advantage: DuoAdvantage;
  };
  ddragonVersion: string;
  isProMode?: boolean;
}

function formatScore(score: number): string {
  return `${(score * 100).toFixed(1)}%`;
}

function advantageLabel(advantage: DuoAdvantage): string {
  if (advantage.stronger_side === "even") {
    return "Équilibré";
  }
  const side = advantage.stronger_side === "blue" ? "Blue" : "Red";
  return `${side} (+${(advantage.difference * 100).toFixed(1)} pt)`;
}

function matchupMethodLabel(method: DuoMatchupDetail["method"]): string {
  if (method === "measured") {
    return "2v2 pro mesuré";
  }
  if (method === "blended") {
    return "2v2 pro + soloQ";
  }
  return "estimation soloQ";
}

function DuoPair({
  label,
  duo,
  side,
  ddragonVersion,
  isProMode = false,
}: {
  label: string;
  duo: DuoSynergyDetail;
  side: "blue" | "red";
  ddragonVersion: string;
  isProMode?: boolean;
}) {
  const [first, second] = duo.champions;
  const scoreExplanation = explainDuoSynergyScore(duo, label, isProMode);
  const insufficient = duo.insufficient_data || duo.score === null;

  return (
    <div className={`duo-card duo-card--${side}${insufficient ? " duo-card--insufficient" : ""}`}>
      <span className="duo-card__label">{label}</span>
      <div className="duo-card__pair">
        <ChampionIcon championName={first} version={ddragonVersion} size={44} side={side} />
        <span className="duo-card__plus">+</span>
        <ChampionIcon championName={second} version={ddragonVersion} size={44} side={side} />
      </div>
      <div className="duo-card__meta">
        {insufficient ? (
          <span className="insufficient-data">{INSUFFICIENT_DATA_LABEL}</span>
        ) : (
          <>
            <strong>{formatScore(duo.score!)}</strong>
            {!duo.is_fallback && duo.games > 0 && (
              <span className="duo-card__games">{duo.games} games pro</span>
            )}
            {duo.is_fallback && <span className="duo-card__badge">estimation Meraki</span>}
          </>
        )}
      </div>
      <p className="duo-card__explanation">{scoreExplanation}</p>
    </div>
  );
}

function DuoMatchupCard({
  title,
  hint,
  matchup,
  ddragonVersion,
  explanation,
  blueDuo,
  redDuo,
  isProMode = false,
}: {
  title: string;
  hint: string;
  matchup: DuoMatchupDetail;
  ddragonVersion: string;
  explanation: MatchupExplanation | null;
  blueDuo?: DuoSynergyDetail;
  redDuo?: DuoSynergyDetail;
  isProMode?: boolean;
}) {
  const [blueFirst, blueSecond] = matchup.blue_champions;
  const [redFirst, redSecond] = matchup.red_champions;
  const headToHeadMeasured =
    !matchup.insufficient_data && matchup.blue_win_probability !== null;
  const redWinProbability =
    matchup.blue_win_probability === null ? null : 1 - matchup.blue_win_probability;

  const blueSideInsufficient =
    isProMode && !headToHeadMeasured
      ? !blueDuo || blueDuo.insufficient_data || blueDuo.score === null
      : !headToHeadMeasured;
  const redSideInsufficient =
    isProMode && !headToHeadMeasured
      ? !redDuo || redDuo.insufficient_data || redDuo.score === null
      : !headToHeadMeasured;

  const cardInsufficient =
    !isProMode && (matchup.insufficient_data || matchup.blue_win_probability === null);

  return (
    <div className={`duo-matchup${cardInsufficient ? " duo-matchup--insufficient" : ""}`}>
      <div className="duo-matchup__header">
        <span className="duo-matchup__title">{title}</span>
        <span className="duo-matchup__method">
          {headToHeadMeasured
            ? matchupMethodLabel(matchup.method)
            : isProMode
              ? "synergie duo interne (pro)"
              : matchupMethodLabel(matchup.method)}
        </span>
      </div>

      <div className="duo-matchup__versus">
        <div className="duo-matchup__side duo-matchup__side--blue">
          <ChampionIcon championName={blueFirst} version={ddragonVersion} size={40} side="blue" />
          <ChampionIcon championName={blueSecond} version={ddragonVersion} size={40} side="blue" />
          {headToHeadMeasured ? (
            <strong>{formatScore(matchup.blue_win_probability!)}</strong>
          ) : blueSideInsufficient ? (
            <span className="insufficient-data insufficient-data--compact">{INSUFFICIENT_DATA_LABEL}</span>
          ) : (
            <>
              <strong>{formatScore(blueDuo!.score!)}</strong>
              {blueDuo!.games > 0 && (
                <span className="duo-card__games">{blueDuo!.games} games pro</span>
              )}
            </>
          )}
        </div>

        <span className="duo-matchup__vs">vs</span>

        <div className="duo-matchup__side duo-matchup__side--red">
          <ChampionIcon championName={redFirst} version={ddragonVersion} size={40} side="red" />
          <ChampionIcon championName={redSecond} version={ddragonVersion} size={40} side="red" />
          {headToHeadMeasured ? (
            <strong>{formatScore(redWinProbability!)}</strong>
          ) : redSideInsufficient ? (
            <span className="insufficient-data insufficient-data--compact">{INSUFFICIENT_DATA_LABEL}</span>
          ) : (
            <>
              <strong>{formatScore(redDuo!.score!)}</strong>
              {redDuo!.games > 0 && (
                <span className="duo-card__games">{redDuo!.games} games pro</span>
              )}
            </>
          )}
        </div>
      </div>

      <p className="duo-matchup__hint">
        {headToHeadMeasured && matchup.method === "measured" && matchup.games > 0
          ? `Basé sur ${matchup.games} games pro avec ce 2v2 exact.`
          : isProMode && !headToHeadMeasured
            ? "Winrate de synergie interne par équipe (Oracle's Elixir). Comparaison 2v2 directe indisponible."
            : cardInsufficient
              ? INSUFFICIENT_DATA_LABEL
              : hint}
      </p>

      {explanation && (
        <div className="duo-matchup__explanation">
          <h5 className="duo-matchup__explanation-title">{explanation.title}</h5>
          <p className="duo-matchup__explanation-body">{explanation.body}</p>
          <p className="duo-matchup__explanation-disclaimer">{explanation.disclaimer}</p>
        </div>
      )}
    </div>
  );
}

function AdvantageRow({
  title,
  advantage,
}: {
  title: string;
  advantage: DuoAdvantage;
}) {
  const explanation = explainDuoAdvantage(
    title,
    advantage.stronger_side,
    advantage.difference,
    advantage.insufficient_data,
    advantage.comparison_message,
  );

  return (
    <div
      className={`duo-advantage${
        advantage.insufficient_data ? " duo-advantage--insufficient" : ""
      }`}
    >
      <div className="duo-advantage__head">
        <span className="duo-advantage__title">{title}</span>
      </div>
      <strong
        className={`duo-advantage__value ${
          advantage.insufficient_data
            ? "insufficient-data"
            : advantage.stronger_side !== "even"
              ? `duo-advantage__value--${advantage.stronger_side}`
              : ""
        }`}
      >
        {advantage.insufficient_data
          ? advantage.comparison_message ?? "N/A"
          : advantageLabel(advantage)}
      </strong>
      <p className="duo-advantage__explanation">{explanation}</p>
      <p className="duo-advantage__method">{DUO_ADVANTAGE_METHODOLOGY}</p>
    </div>
  );
}

export function DuoSynergiesSection({
  blueTeam,
  redTeam,
  duoSynergies,
  botLaneMatchup,
  jungleSupportMatchup,
  duoDifferential,
  ddragonVersion,
  isProMode = false,
}: DuoSynergiesSectionProps) {
  const [merakiCatalog, setMerakiCatalog] = useState<MerakiChampionCatalog | null>(null);

  useEffect(() => {
    let cancelled = false;

    loadMerakiChampionCatalog()
      .then((catalog) => {
        if (!cancelled) {
          setMerakiCatalog(catalog);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMerakiCatalog(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const jungleExplanation = useMemo(
    () =>
      merakiCatalog
        ? generateMatchupExplanation(jungleSupportMatchup, "jungle_support", merakiCatalog)
        : null,
    [jungleSupportMatchup, merakiCatalog],
  );

  const botExplanation = useMemo(
    () =>
      merakiCatalog ? generateMatchupExplanation(botLaneMatchup, "bot_lane", merakiCatalog) : null,
    [botLaneMatchup, merakiCatalog],
  );

  const duoMethodology = isProMode ? DUO_SECTION_METHODOLOGY_PRO : DUO_SECTION_METHODOLOGY;

  return (
    <section className="draft-result__duos">
      <h3 className="draft-result__section-title">Synergies de duo</h3>
      <MethodologyNote variant="compact">
        <p>{duoMethodology.body}</p>
      </MethodologyNote>

      <TeamSynergySection
        blueTeam={blueTeam}
        redTeam={redTeam}
        ddragonVersion={ddragonVersion}
      />

      <div className="duo-matchups">
        <DuoMatchupCard
          title="Matchup jungle-support 2v2"
          hint={
            isProMode
              ? "Winrate 2v2 mesuré en pro uniquement (Oracle's Elixir)."
              : "Estimation soloQ (impact jungle + support) ajustée par la synergie interne de chaque duo."
          }
          matchup={jungleSupportMatchup}
          ddragonVersion={ddragonVersion}
          explanation={jungleExplanation}
          blueDuo={duoSynergies.blue.duo_jungle_support}
          redDuo={duoSynergies.red.duo_jungle_support}
          isProMode={isProMode}
        />
        <DuoMatchupCard
          title="Matchup bot lane 2v2"
          hint={
            isProMode
              ? "Winrate 2v2 mesuré en pro uniquement (Oracle's Elixir)."
              : "Estimation soloQ (lane + counters adc/sup) ajustée par la synergie interne de chaque duo."
          }
          matchup={botLaneMatchup}
          ddragonVersion={ddragonVersion}
          explanation={botExplanation}
          blueDuo={duoSynergies.blue.duo_bot_lane}
          redDuo={duoSynergies.red.duo_bot_lane}
          isProMode={isProMode}
        />
      </div>

      <div className="duo-grid">
        <div className="duo-grid__team">
          <h4 className="duo-grid__team-title duo-grid__team-title--blue">Blue</h4>
          <DuoPair
            label="Jungle + Support"
            duo={duoSynergies.blue.duo_jungle_support}
            side="blue"
            ddragonVersion={ddragonVersion}
            isProMode={isProMode}
          />
          <DuoPair
            label="Bot lane"
            duo={duoSynergies.blue.duo_bot_lane}
            side="blue"
            ddragonVersion={ddragonVersion}
            isProMode={isProMode}
          />
        </div>

        <div className="duo-grid__team">
          <h4 className="duo-grid__team-title duo-grid__team-title--red">Red</h4>
          <DuoPair
            label="Jungle + Support"
            duo={duoSynergies.red.duo_jungle_support}
            side="red"
            ddragonVersion={ddragonVersion}
            isProMode={isProMode}
          />
          <DuoPair
            label="Bot lane"
            duo={duoSynergies.red.duo_bot_lane}
            side="red"
            ddragonVersion={ddragonVersion}
            isProMode={isProMode}
          />
        </div>
      </div>

      <div className="duo-advantages">
        <AdvantageRow
          title="Avantage jungle-support"
          advantage={duoDifferential.jungle_support_advantage}
        />
        <AdvantageRow
          title="Avantage bot lane"
          advantage={duoDifferential.bot_lane_advantage}
        />
      </div>
    </section>
  );
}
