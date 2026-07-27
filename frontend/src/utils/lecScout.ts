import type { LecScoutDossier, LecTeamIdentity } from "../types/lec";

const SCOUT_QUESTIONS: Record<
  string,
  { prompt: string; hintFromIdentity: (identity: LecTeamIdentity) => string }[]
> = {
  default: [
    {
      prompt: "Quel est leur tempo de draft ?",
      hintFromIdentity: (identity) =>
        `Le staff parle d'un style « ${identity.label} » — repère leurs tags ${identity.tags.slice(0, 2).join(" / ")}.`,
    },
    {
      prompt: "Qui est le carry principal ?",
      hintFromIdentity: (identity) =>
        identity.tags.includes("scaling")
          ? "Le win condition semble late — protège leur scaling."
          : "Ils cherchent probablement l'early sur une lane prioritaire.",
    },
    {
      prompt: "Quels bans les rendent inconfortables ?",
      hintFromIdentity: (identity) =>
        `Viser leurs forces ${identity.ban_bias.join(" et ")} peut les déstabiliser.`,
    },
  ],
};

export function createScoutDossier(teamId: string): LecScoutDossier {
  return { teamId, hints: [], familiarity: 0 };
}

export function discussWithStaff(
  dossier: LecScoutDossier,
  identity: LecTeamIdentity,
  questionIndex: number,
): { dossier: LecScoutDossier; line: string } {
  const questions = SCOUT_QUESTIONS.default;
  const question = questions[questionIndex % questions.length];
  const hint = question.hintFromIdentity(identity);
  if (dossier.hints.includes(hint)) {
    return {
      dossier,
      line: "Ton staff n'a rien de neuf sur ce point pour l'instant.",
    };
  }
  return {
    dossier: {
      ...dossier,
      hints: [...dossier.hints, hint],
      familiarity: dossier.familiarity + 1,
    },
    line: hint,
  };
}

export function familiarityLabel(familiarity: number): string {
  if (familiarity >= 4) {
    return "Dossier avancé";
  }
  if (familiarity >= 2) {
    return "Dossier partiel";
  }
  if (familiarity >= 1) {
    return "Premiers indices";
  }
  return "Peu d'infos";
}
