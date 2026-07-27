import type { LecPlayerProfile, LecScoutDossier, LecTeamIdentity } from "../types/lec";

export type ScoutAction = "style" | "picks";

export function createScoutDossier(teamId: string): LecScoutDossier {
  return {
    teamId,
    styleRevealed: false,
    revealedPicks: [],
    familiarity: 0,
  };
}

export function migrateScoutDossier(raw: Partial<LecScoutDossier> & { hints?: string[] }): LecScoutDossier {
  if (raw.styleRevealed !== undefined || raw.revealedPicks) {
    return {
      teamId: raw.teamId ?? "",
      styleRevealed: Boolean(raw.styleRevealed),
      revealedPicks: raw.revealedPicks ?? [],
      familiarity: raw.familiarity ?? 0,
    };
  }
  return {
    teamId: raw.teamId ?? "",
    styleRevealed: (raw.hints?.length ?? 0) > 0,
    revealedPicks: [],
    familiarity: raw.familiarity ?? 0,
  };
}

export function scoutPickCandidates(profiles: LecPlayerProfile[]): Array<{
  player: string;
  role: string;
  champion: string;
}> {
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

  if (dossier.revealedPicks.length >= 2) {
    return {
      dossier,
      line: "Ton staff n'a plus d'info fiable sur leurs picks favoris.",
    };
  }

  const already = new Set(dossier.revealedPicks.map((entry) => `${entry.role}:${entry.champion}`));
  const candidates = scoutPickCandidates(profiles);

  const next = candidates.find(
    (entry) => !already.has(`${entry.role}:${entry.champion}`),
  );

  if (!next) {
    return {
      dossier,
      line: "Aucun pick favori identifié pour l'instant.",
    };
  }

  return {
    dossier: {
      ...dossier,
      revealedPicks: [...dossier.revealedPicks, next],
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
