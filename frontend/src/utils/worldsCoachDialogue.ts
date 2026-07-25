import type { WorldsTeam } from "../types/worlds";

const TEAM_LINES: Record<
  string,
  {
    intro: string[];
    thinking: string[];
    ban: string[];
    pick: string[];
    playerTurn: string[];
  }
> = {
  t1: {
    intro: [
      "Tom mène la draft aujourd'hui. T1 ne teste rien — tempo et signatures.",
      "Interim ou pas, la discipline T1 reste la même. Prépare-toi.",
    ],
    thinking: ["Oner réfléchit à la jungle path…", "Keria lit ton ban avant que tu cliques."],
    ban: ["On retire ton confort — standard T1.", "Ce ban protège le plan de Faker."],
    pick: ["Signature T1. Keria l'a demandé.", "Oner est confortable là-dessus, next."],
    playerTurn: ["À toi. Montre-moi si tu connais nos habits.", "Ton tour — T1 observe."],
  },
  geng: {
    intro: [
      "Gen.G sous Ryu — draft structurée, Chovy ne pardonne pas les erreurs.",
      "Nouvelle ère Gen.G. On teste ta macro dès le ban 1.",
    ],
    thinking: ["Canyon calcule le tempo jungle…", "Chovy prépare sa réponse mid."],
    ban: ["On cible ta win condition.", "Gen.G ban data-driven."],
    pick: ["Pool Chovy. Classique.", "Canyon synergy — on verrouille."],
    playerTurn: ["Ton move. Gen.G s'adapte vite.", "Ne nous sous-estime pas."],
  },
  blg: {
    intro: [
      "Daeny mène BLG — LPL Split 1 & 2 champions. Knight veut le mid prio.",
      "On a gagné First Stand. Tu vas sentir la pression draft BLG.",
    ],
    thinking: ["Knight hover…", "Xun cherche l'angle d'invade."],
    ban: ["BLG retire ta ligne de comfort.", "Ban orienté tempo LPL."],
    pick: ["Knight signature.", "Bin peut carry sur ça."],
    playerTurn: ["Draft vite — BLG n'attend pas.", "Ton tour, challenger."],
  },
  g2: {
    intro: [
      "Perkz est de retour — en tant que head coach cette fois. Caps et moi, on connaît la recette.",
      "J'ai déjà carry G2 en mid. Maintenant je carry la draft. Bonne chance.",
    ],
    thinking: ["Perkz calcule le flex mid…", "G2 prépare le chaos contrôlé de Caps."],
    ban: ["Ban G2 — je connais tes comfort picks.", "Retiré. On a déjà vu ce film en LEC."],
    pick: ["Caps special. L'histoire G2 continue.", "Pick signature — Perkz approuve."],
    playerTurn: ["À toi. Montre-moi si tu outdraft Perkz.", "Ton tour — G2 love les mind games."],
  },
  hle: {
    intro: [
      "Homme est aux commandes — MSI 2026 champions. Kanavi-Zeus veulent l'early.",
      "HLE stack les stars. Zeka attend son moment pour carry.",
    ],
    thinking: ["Kanavi pathing…", "Zeus demande un counter pick?"],
    ban: ["On protège nos carries.", "Ban HLE — pas de cadeau."],
    pick: ["Zeus comfort.", "Zeka peut 1v9 sur ce pick."],
    playerTurn: ["Ton tour. HLE punira les erreurs.", "Draft sérieuse maintenant."],
  },
  tes: {
    intro: [
      "Poppy mène TES — JackeyLove veut le bot prio, Creme le mid.",
      "Tian va chercher le tempo jungle dès les bans.",
    ],
    thinking: ["Tian réfléchit…", "Creme hover mid."],
    ban: ["TES retire ta wincon bot.", "Ban LPL — tempo first."],
    pick: ["JackeyLove pool.", "Tian synergy lock."],
    playerTurn: ["Draft TES incoming… ton move.", "Poppy observe ton plan."],
  },
  dk: {
    intro: [
      "cvMax est de retour sur DK — macro agressive, ShowMaker au centre.",
      "Lucid cherche le tempo, Smash scale en bot. Pas de free farm.",
    ],
    thinking: ["ShowMaker lit la comp…", "DK prépare le tempo early."],
    ban: ["Ban macro DK.", "ShowMaker ne veut pas voir ce champ."],
    pick: ["ShowMaker pick. DK classic.", "Lucid happy."],
    playerTurn: ["À toi. DK punira les erreurs de draft.", "Ne scale pas gratuitement."],
  },
};

const DEFAULT_LINES = {
  intro: ["Draft importante. Pas de seconde chance."],
  thinking: ["Réflexion en cours…"],
  ban: ["Ban ciblé."],
  pick: ["Pick cohérent avec notre plan."],
  playerTurn: ["À toi."],
};

function pickRandom(lines: string[]): string {
  return lines[Math.floor(Math.random() * lines.length)] ?? lines[0] ?? "";
}

export type CoachDialogueEvent =
  | { type: "intro" }
  | { type: "thinking" }
  | { type: "ban"; champion: string }
  | { type: "pick"; champion: string }
  | { type: "player_turn" }
  | { type: "error"; detail?: string | null };

export function coachLineForTeam(team: WorldsTeam, event: CoachDialogueEvent): string {
  const lines = TEAM_LINES[team.id] ?? DEFAULT_LINES;

  switch (event.type) {
    case "intro":
      return pickRandom(lines.intro);
    case "thinking":
      return pickRandom(lines.thinking);
    case "ban":
      return `${pickRandom(lines.ban)} (${event.champion})`;
    case "pick":
      return `${pickRandom(lines.pick)} — ${event.champion}`;
    case "player_turn":
      return pickRandom(lines.playerTurn);
    case "error":
      return event.detail?.trim() || "Erreur technique — on relance le client draft.";
    default:
      return pickRandom(lines.intro);
  }
}

export function regionAccentClass(region: string): string {
  switch (region) {
    case "LCK":
      return "worlds-coach--lck";
    case "LPL":
      return "worlds-coach--lpl";
    case "LEC":
      return "worlds-coach--lec";
    default:
      return "worlds-coach--custom";
  }
}

const COACH_PORTRAITS: Record<string, string> = {
  t1: "/coaches/tom.jpg",
  geng: "/coaches/ryu.jpg",
  blg: "/coaches/daeny.jpg",
  g2: "/coaches/perkz.jpg",
  hle: "/coaches/homme.jpg",
  tes: "/coaches/poppy.jpg",
  dk: "/coaches/cvmax.jpg",
};

export function coachPortraitUrl(team: WorldsTeam): string | null {
  if (team.coach_portrait) {
    return team.coach_portrait;
  }
  return COACH_PORTRAITS[team.id] ?? null;
}
