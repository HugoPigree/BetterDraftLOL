import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import type { DraftAnalysisBundle } from "../utils/generateAnalysis";
import { translateMerakiRoleLabel } from "../utils/generateAnalysis";
import type { PredictResponse, TeamPredictionDetail } from "../types/predict";
import { ATTRIBUTE_KEYS, ATTRIBUTE_LABELS } from "../types/predict";

interface AttributeRadarChartProps {
  blue: TeamPredictionDetail;
  red: TeamPredictionDetail;
}

function buildRadarData(blue: TeamPredictionDetail, red: TeamPredictionDetail) {
  return ATTRIBUTE_KEYS.map((key) => ({
    attribute: ATTRIBUTE_LABELS[key],
    blue: blue.attribute_profile[key],
    red: red.attribute_profile[key],
  }));
}

export function AttributeRadarChart({ blue, red }: AttributeRadarChartProps) {
  const data = buildRadarData(blue, red);
  const maxValue = Math.max(
    3,
    ...data.flatMap((entry) => [entry.blue, entry.red]),
  );

  return (
    <div className="draft-result__radar">
      <h3 className="draft-result__section-title">Profil d&apos;attributs</h3>
      <p className="draft-result__section-subtitle">
        Profils Meraki moyens (échelle 0–3). Compare la forme de la compo, pas la force brute soloQ.
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="rgba(255,255,255,0.12)" />
          <PolarAngleAxis
            dataKey="attribute"
            tick={{ fill: "#a09b8c", fontSize: 11, fontFamily: "Rajdhani, Segoe UI, sans-serif" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, maxValue]}
            tick={{ fill: "#666", fontSize: 10 }}
            stroke="rgba(255,255,255,0.08)"
          />
          <Radar
            name="Blue"
            dataKey="blue"
            stroke="#5bb8f0"
            fill="#3a9fd9"
            fillOpacity={0.28}
            strokeWidth={2}
          />
          <Radar
            name="Red"
            dataKey="red"
            stroke="#e86060"
            fill="#c84b4b"
            fillOpacity={0.22}
            strokeWidth={2}
          />
          <Legend
            wrapperStyle={{ fontSize: "12px", fontFamily: "Rajdhani, Segoe UI, sans-serif" }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

function winrateClass(winrate: number): string {
  if (winrate > 0.52) {
    return "draft-result__winrate--strong";
  }
  if (winrate < 0.48) {
    return "draft-result__winrate--weak";
  }
  return "";
}

function formatWinratePercent(winrate: number): string {
  return `${(winrate * 100).toFixed(1)}%`;
}

interface TeamChampionTableProps {
  team: TeamPredictionDetail;
  side: "blue" | "red";
  label: string;
}

export function TeamChampionTable({ team, side, label }: TeamChampionTableProps) {
  const champions = [...team.champions].sort((a, b) => b.winrate - a.winrate);

  return (
    <div className={`draft-result__table draft-result__table--${side}`}>
      <h3 className="draft-result__section-title">{label}</h3>
      <table>
        <thead>
          <tr>
            <th>Champion</th>
            <th>Rôle</th>
            <th>WR SoloQ</th>
          </tr>
        </thead>
        <tbody>
          {champions.map((entry) => (
            <tr key={`${entry.champion}-${entry.role}`}>
              <td>{entry.champion}</td>
              <td>{entry.role}</td>
              <td className={winrateClass(entry.winrate)}>{formatWinratePercent(entry.winrate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface TeamRoleBadgesProps {
  roles: PredictResponse["blue"]["meraki_roles"];
  side: "blue" | "red";
  label: string;
}

export function TeamRoleBadges({ roles, side, label }: TeamRoleBadgesProps) {
  return (
    <div className={`draft-result__roles draft-result__roles--${side}`}>
      <h4>{label}</h4>
      <div className="draft-result__role-tags">
        {roles.length === 0 ? (
          <span className="draft-result__role-tag draft-result__role-tag--empty">Aucun rôle</span>
        ) : (
          roles.map((entry) => (
            <span key={entry.role} className="draft-result__role-tag">
              {entry.count}× {translateMerakiRoleLabel(entry.role)}
            </span>
          ))
        )}
      </div>
    </div>
  );
}

interface DraftResultDetailsProps {
  result: PredictResponse;
  analysisBundle: DraftAnalysisBundle;
}

export function DraftResultDetails({ result, analysisBundle }: DraftResultDetailsProps) {
  return (
    <div className="draft-result__details">
      <div className="draft-result__insights-grid">
        <AttributeRadarChart blue={result.blue} red={result.red} />
        <div className="draft-result__tables">
          <TeamChampionTable team={result.blue} side="blue" label="Blue — Winrates soloQ" />
          <TeamChampionTable team={result.red} side="red" label="Red — Winrates soloQ" />
        </div>
      </div>

      <div className="draft-result__roles-row">
        <TeamRoleBadges roles={result.blue.meraki_roles} side="blue" label="Archétypes Blue" />
        <TeamRoleBadges roles={result.red.meraki_roles} side="red" label="Archétypes Red" />
      </div>

      <div className="draft-result__affinity-row">
        <div className="draft-result__affinity draft-result__affinity--blue">
          <h3 className="draft-result__section-title">{analysisBundle.blueAffinity.title}</h3>
          {analysisBundle.blueAffinity.lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
        <div className="draft-result__affinity draft-result__affinity--red">
          <h3 className="draft-result__section-title">{analysisBundle.redAffinity.title}</h3>
          {analysisBundle.redAffinity.lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      </div>

      <div className="draft-result__matchups">
        <h3 className="draft-result__section-title">Matchups par rôle (soloQ)</h3>
        <p className="draft-result__section-subtitle">
          Comparaison pick vs pick sur le même rôle. Proxy de avantage de lane, pas un vrai counter matchup.
        </p>
        <div className="draft-result__matchup-list">
          {analysisBundle.laneMatchups.map((matchup) => (
            <article
              key={matchup.role}
              className={`draft-result__matchup-card ${
                Math.abs(matchup.deltaPoints) >= 4
                  ? matchup.deltaPoints > 0
                    ? "draft-result__matchup-card--blue"
                    : "draft-result__matchup-card--red"
                  : ""
              }`}
            >
              <span className="draft-result__matchup-role">{matchup.roleLabel}</span>
              <p>{matchup.summary}</p>
            </article>
          ))}
        </div>
      </div>

      <div className="draft-result__analysis">
        <h3 className="draft-result__section-title">Synthèse</h3>
        {analysisBundle.summary.map((sentence) => (
          <p key={sentence}>{sentence}</p>
        ))}
      </div>
    </div>
  );
}
