import { ChampionIcon } from "./ChampionIcon";
import { TeamRoleBadges } from "./DraftResultDetails";
import type { TeamPredictionDetail } from "../types/predict";
import { generateTeamSynergyExplanation } from "../utils/generateTeamSynergyExplanation";

const ROLE_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"] as const;

function formatSynergyScore(score: number): string {
  return `${(score * 100).toFixed(1)}%`;
}

function championsInRoleOrder(team: TeamPredictionDetail) {
  const byRole = new Map(team.champions.map((entry) => [entry.role, entry.champion]));
  return ROLE_ORDER.map((role) => ({
    role,
    champion: byRole.get(role) ?? null,
  }));
}

function TeamSynergySideCard({
  team,
  side,
  label,
  ddragonVersion,
}: {
  team: TeamPredictionDetail;
  side: "blue" | "red";
  label: string;
  ddragonVersion: string;
}) {
  const lineup = championsInRoleOrder(team);
  const explanation = generateTeamSynergyExplanation(team.synergy_insight);

  return (
    <div className={`team-synergy-card team-synergy-card--${side}`}>
      <span className="team-synergy-card__team-label">{label}</span>
      <div className="team-synergy-card__score-row">
        <strong className="team-synergy-card__score">{formatSynergyScore(team.score_synergie)}</strong>
        <span className="team-synergy-card__score-caption">synergie globale</span>
      </div>

      <div className="team-synergy-card__lineup">
        {lineup.map(({ role, champion }) =>
          champion ? (
            <ChampionIcon
              key={role}
              championName={champion}
              version={ddragonVersion}
              size={44}
              side={side}
              role={role}
            />
          ) : (
            <span key={role} className="team-synergy-card__missing" title={role}>
              ?
            </span>
          ),
        )}
      </div>

      <TeamRoleBadges roles={team.meraki_roles} side={side} label="Archétypes Meraki" />

      <p className="team-synergy-card__explanation">{explanation}</p>
    </div>
  );
}

interface TeamSynergySectionProps {
  blueTeam: TeamPredictionDetail;
  redTeam: TeamPredictionDetail;
  ddragonVersion: string;
}

export function TeamSynergySection({
  blueTeam,
  redTeam,
  ddragonVersion,
}: TeamSynergySectionProps) {
  return (
    <div className="team-synergy-section">
      <h4 className="team-synergy-section__title">Synergie globale de l&apos;équipe</h4>
      <div className="team-synergy-section__grid">
        <TeamSynergySideCard
          team={blueTeam}
          side="blue"
          label="Blue"
          ddragonVersion={ddragonVersion}
        />
        <TeamSynergySideCard
          team={redTeam}
          side="red"
          label="Red"
          ddragonVersion={ddragonVersion}
        />
      </div>
    </div>
  );
}
