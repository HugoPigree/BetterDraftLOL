import type { LecTeam } from "../types/lec";
import { bundledCoachPortraitUrl } from "./coachPortraits";

export function lecTeamBadgeLabel(team: Pick<LecTeam, "short_name" | "name">): string {
  return team.short_name ?? team.name.slice(0, 3).toUpperCase();
}

export function lecTeamColor(team: Pick<LecTeam, "brand_color">): string {
  return team.brand_color ?? "#6B7280";
}

export function lecCoachPortrait(team: LecTeam): string | null {
  return bundledCoachPortraitUrl(team.id, team.coach);
}

export function findLecTeam(teams: LecTeam[], teamId: string): LecTeam | null {
  return teams.find((team) => team.id === teamId) ?? null;
}

export function opponentForFixture(
  teams: LecTeam[],
  fixture: { team_a_id: string; team_b_id: string },
  playerTeamId = "player",
): LecTeam | null {
  const opponentId =
    fixture.team_a_id === playerTeamId ? fixture.team_b_id : fixture.team_a_id;
  return findLecTeam(teams, opponentId);
}
