import type { LecStoryChapter } from "../types/lec";

export const LEC_STORY_CHAPTERS: LecStoryChapter[] = [
  {
    id: "intro-1",
    title: "Berlin t'attend",
    trigger: "intro",
    lines: [
      {
        speaker: "Narrateur",
        text: "Berlin, Riot Games Arena. Les projecteurs s'allument sur une nouvelle saison LEC. Tu viens de fonder ton projet — une équipe avec une identité, un coach, et l'ambition de gratter une place aux Worlds.",
        mood: "neutral",
      },
      {
        speaker: "Coach",
        text: "On ne viendra pas pour faire de la figuration. Chaque Bo1 compte. Neuf semaines pour imposer notre tempo, puis les playoffs. Top 3 = Worlds. C'est clair ?",
        mood: "tension",
      },
      {
        speaker: "Capitaine",
        text: "On connaît la route. Draft propre, exécution froide. Si on maîtrise la meta avant les autres, personne ne nous arrêtera en phase régulière.",
        mood: "triumph",
      },
    ],
  },
  {
    id: "week-3",
    title: "Premier check-up",
    trigger: "week",
    triggerWeek: 3,
    lines: [
      {
        speaker: "Analyste",
        text: "Trois semaines de LEC. Le classement se dessine : Fnatic et Karmine Corp imposent déjà leur rythme, G2 rôde. Notre diff de draft commence à parler en votre faveur.",
        mood: "neutral",
      },
      {
        speaker: "Coach",
        text: "Les semaines faciles n'existent pas. Mais je vois une équipe qui comprend quand engage et quand temporiser. Continuez sur cette ligne.",
        mood: "tension",
      },
    ],
  },
  {
    id: "week-6",
    title: "La ligne droite",
    trigger: "week",
    triggerWeek: 6,
    lines: [
      {
        speaker: "Journaliste LEC",
        text: "La course aux playoffs entre dans sa phase décisive. Six équipes passeront. Le reste rentrera chez soi sans ticket pour le bracket.",
        mood: "tension",
      },
      {
        speaker: "Rival",
        portraitTeamId: "g2",
        text: "L'Europe a l'habitude de sous-estimer les nouvelles structures… jusqu'à ce qu'elles vous renversent en draft. On se voit sur la faille.",
        mood: "tension",
      },
    ],
  },
  {
    id: "playoffs",
    title: "Playoffs — Bo3",
    trigger: "playoffs",
    lines: [
      {
        speaker: "Narrateur",
        text: "La phase régulière est derrière vous. Le Berlin Playoffs Hub vibre. Les séries passent en Bo3, puis Bo5 en finale. Chaque draft peut éliminer une saison entière.",
        mood: "tension",
      },
      {
        speaker: "Coach",
        text: "Respirez. On a mérité notre place. Maintenant, on joue comme si c'était une finale de Worlds — parce que pour certains, ça l'est.",
        mood: "triumph",
      },
    ],
  },
  {
    id: "worlds",
    title: "Qualifié pour Worlds",
    trigger: "worlds",
    lines: [
      {
        speaker: "Narrateur",
        text: "Top 3 LEC. Le drapeau européen est à vous. Dans quelques semaines, la scène internationale vous attendra — mais ce soir, Berlin applaudit.",
        mood: "triumph",
      },
      {
        speaker: "Coach",
        text: "On a prouvé qu'on pouvait draft, exécuter, tenir la pression. Les Worlds, c'est la même recette… avec le monde entier en face.",
        mood: "triumph",
      },
    ],
  },
  {
    id: "missed-worlds",
    title: "Saison terminée",
    trigger: "eliminated",
    lines: [
      {
        speaker: "Coach",
        text: "Pas de Worlds cette année. Ça pique. Mais une carrière se construit sur plusieurs saisons — analyse, recrutement, et retour plus fort.",
        mood: "doubt",
      },
      {
        speaker: "Narrateur",
        text: "La LEC continue sans vous sur la scène internationale. Pourtant, votre projet existe, grandit. La prochaine saison commencera avec des leçons, pas des regrets.",
        mood: "neutral",
      },
    ],
  },
];

export function storyChapterForWeek(week: number): LecStoryChapter | null {
  return (
    LEC_STORY_CHAPTERS.find(
      (chapter) => chapter.trigger === "week" && chapter.triggerWeek === week,
    ) ?? null
  );
}

export function storyChapterById(id: string): LecStoryChapter | null {
  return LEC_STORY_CHAPTERS.find((chapter) => chapter.id === id) ?? null;
}
