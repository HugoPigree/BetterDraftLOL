import type {
  LecCareerUniverse,
  LecPlayerProfile,
  LecScoutDossier,
  LecTeamIdentity,
  LecTeamPreferredPick,
} from "../types/lec";
import preferredPickData from "../data/careerTeamPreferredPicks.json";

export type ScoutAction = "style" | "picks";

const SCOUT_ROLE_ORDER = ["JUNGLE", "MIDDLE", "BOTTOM", "TOP", "UTILITY"] as const;

type ScoutPickCandidate = {
  player: string;
  role: string;
  champion: string;
};

export function createScoutDossier(teamId: string): LecScoutDossier {
  return {
    teamId,
    styleRevealed: false,
    revealedPicks: [],
    familiarity: 0,
  };
}

function sanitizeRevealedPicks(
  picks: LecScoutDossier["revealedPicks"],
): LecScoutDossier["revealedPicks"] {
  const seenRoles = new Set<string>();
  const sanitized: LecScoutDossier["revealedPicks"] = [];
  for (const pick of picks) {
    if (seenRoles.has(pick.role) || sanitized.length >= 2) {
      continue;
    }
    seenRoles.add(pick.role);
    sanitized.push(pick);
  }
  return sanitized;
}

export function migrateScoutDossier(raw: Partial<LecScoutDossier> & { hints?: string[] }): LecScoutDossier {
  const revealedPicks = sanitizeRevealedPicks(raw.revealedPicks ?? []);
  return {
    teamId: raw.teamId ?? "",
    styleRevealed: Boolean(raw.styleRevealed),
    revealedPicks,
    familiarity: raw.familiarity ?? 0,
  };
}

export function careerUniverseNeedsRepair(universe: LecCareerUniverse | null | undefined): boolean {
  if (!universe) {
    return true;
  }
  if (!universe.team_preferred_picks) {
    return true;
  }
  const profiles = Object.values(universe.team_profiles).flat();
  return profiles.some((profile) => !(profile.signature_picks?.length ?? 0));
}

export function scoutPickCandidates(
  teamId: string,
  profiles: LecPlayerProfile[],
  teamPreferred?: LecTeamPreferredPick[],
): ScoutPickCandidate[] {
  const profileByRole = new Map(profiles.map((profile) => [profile.role, profile]));

  if (teamPreferred?.length) {
    return teamPreferred
      .filter((entry) => entry.champions[0])
      .map((entry) => ({
        player: entry.player,
        role: entry.role,
        champion: entry.champions[0],
      }));
  }

  const filePicks = preferredPickData.teams[teamId as keyof typeof preferredPickData.teams];
  if (filePicks) {
    return SCOUT_ROLE_ORDER.flatMap((role) => {
      const champion = filePicks[role as keyof typeof filePicks]?.[0];
      const profile = profileByRole.get(role);
      if (!champion || !profile) {
        return [];
      }
      return [{ player: profile.player, role, champion }];
    });
  }

  return profiles.flatMap((profile) => {
    const champion = profile.signature_picks?.[0] ?? profile.comfort?.[0];
    if (!champion) {
      return [];
    }
    return [{ player: profile.player, role: profile.role, champion }];
  });
}

export function discussWithStaff(
  dossier: LecScoutDossier,
  identity: LecTeamIdentity,
  profiles: LecPlayerProfile[],
  action: ScoutAction,
  teamId: string,
  teamPreferred?: LecTeamPreferredPick[],
): { dossier: LecScoutDossier; line: string } {
  if (action === "style") {
    if (dossier.styleRevealed) {
      return {
        dossier,
        line: `Style confirmé : ${identity.label} (${identity.tags.slice(0, 2).join(", ")}).`,
      };
    }
    return {
      dossier: {
        ...dossier,
        styleRevealed: true,
        familiarity: dossier.familiarity + 1,
      },
      line: `Style repéré : ${identity.label}. Ils privilégient ${identity.tags.slice(0, 2).join(" et ")}.`,
    };
  }

  const sanitizedPicks = sanitizeRevealedPicks(dossier.revealedPicks);
  const revealedRoles = new Set(sanitizedPicks.map((pick) => pick.role));

  if (sanitizedPicks.length >= 2) {
    return {
      dossier: { ...dossier, revealedPicks: sanitizedPicks },
      line: "Ton staff n'a plus d'info fiable sur leurs picks favoris.",
    };
  }

  const candidates = scoutPickCandidates(teamId, profiles, teamPreferred);
  const next = candidates.find((entry) => !revealedRoles.has(entry.role));

  if (!next) {
    return {
      dossier: { ...dossier, revealedPicks: sanitizedPicks },
      line: "Aucun pick favori identifié pour l'instant.",
    };
  }

  return {
    dossier: {
      ...dossier,
      revealedPicks: sanitizeRevealedPicks([...sanitizedPicks, next]),
      familiarity: dossier.familiarity + 1,
    },
    line: `Pick favori repéré : ${next.player} (${next.role}) — ${next.champion}.`,
  };
}

export function familiarityLabel(familiarity: number): string {
  if (familiarity >= 3) {
    return "Dossier solide";
  }
  if (familiarity >= 2) {
    return "Dossier partiel";
  }
  if (familiarity >= 1) {
    return "Premiers indices";
  }
  return "Peu d'infos";
}
