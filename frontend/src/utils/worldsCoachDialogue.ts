import type { WorldsTeam } from "../types/worlds";
import { bundledCoachPortraitUrl } from "./coachPortraits";

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
      "G2 en mode LEC : flex, tempo, et un peu de chaos contrôlé.",
    ],
    thinking: ["Perkz calcule le flex mid…", "G2 prépare le chaos contrôlé de Caps.", "Labrov cherche le setup bot."],
    ban: ["Ban G2 — je connais tes comfort picks.", "Retiré. On a déjà vu ce film en LEC.", "On coupe ta win condition avant le pick 3."],
    pick: ["Caps special. L'histoire G2 continue.", "Pick signature — Perkz approuve.", "BrokenBlade peut 1-3 sur ça, next."],
    playerTurn: ["À toi. Montre-moi si tu outdraft Perkz.", "Ton tour — G2 love les mind games.", "Draft vite, on lit déjà ton plan."],
  },
  fnatic: {
    intro: [
      "GrabbZ mène Fnatic — discipline LEC, tempo propre.",
      "Oscarinin veut le counter pick top. Upset attend le bot prio.",
      "FNC ne draft pas au feeling. Chaque ban a une raison.",
    ],
    thinking: ["Razork calcule le path jungle…", "Humanoid prépare la réponse mid.", "Mikyx lit ton bot lane."],
    ban: ["On retire ton confort — standard Fnatic.", "Ban data-driven FNC.", "Ce champion ne passera pas."],
    pick: ["Upset pool. Clean.", "Razork synergy — on lock.", "Oscarinin est happy sur ce pick."],
    playerTurn: ["À toi. Montre ta macro draft.", "FNC s'adapte vite.", "Ne nous sous-estime pas en Bo1."],
  },
  kc: {
    intro: [
      "Bubbling et KC — la hype européenne en draft.",
      "Caliste veut le bot carry. Yike cherche l'early tempo.",
      "KC draft agressive. On vient pour ton confort pick.",
    ],
    thinking: ["Yike hover jungle…", "Canna demande un counter?", "Targamas prépare le roam."],
    ban: ["KC retire ta ligne de comfort.", "Ban ciblé — pool Caliste protégé.", "On lit tes habits LEC."],
    pick: ["Pick KC signature.", "Yike peut invade sur ça.", "Caliste carry angle."],
    playerTurn: ["Ton move. KC répond en vitesse.", "Draft sérieuse — Bo1 LEC.", "Montre-nous ta prep."],
  },
  mkoi: {
    intro: [
      "Melia mène MKOI — Elyoya veut le tempo, Jojopyun le mid prio.",
      "KOI draft structurée. Supa scale en bot.",
      "On connaît la meta, on teste ta lecture.",
    ],
    thinking: ["Elyoya pathing…", "Jojopyun cherche le angle mid.", "Alvaro setup bot."],
    ban: ["MKOI ban macro.", "On protège notre wincon.", "Retiré — pas de cadeau."],
    pick: ["Elyoya happy.", "Jojopyun comfort pick.", "Supa peut carry late."],
    playerTurn: ["Ton tour. KOI punira les erreurs.", "Draft MKOI incoming.", "Bo1 — pas de second essai."],
  },
  vitality: {
    intro: [
      "Horcus et Vitality — Carzzy veut le bot, Lyncas le tempo.",
      "VIT draft directe. Naak Nako cherche le side lane.",
    ],
    thinking: ["Lyncas réfléchit…", "Carzzy hover bot.", "Czajek mid prep."],
    ban: ["VIT retire ta wincon.", "Ban LEC — tempo first.", "On coupe ta bot lane."],
    pick: ["Carzzy pool.", "Lyncas synergy.", "VIT classic."],
    playerTurn: ["À toi. VIT observe.", "Draft VIT — montre ton plan.", "Ne scale pas gratuitement."],
  },
  giantx: {
    intro: [
      "Guilhoto mène GIANTX — macro européenne propre.",
      "Isma cherche le tempo jungle, Noah le bot scaling.",
    ],
    thinking: ["Isma calcule…", "Jackies mid hover.", "Jun prépare le setup."],
    ban: ["GX ban ciblé.", "On protège le plan.", "Retiré proprement."],
    pick: ["GX pick cohérent.", "Noah scale.", "Isma pathing lock."],
    playerTurn: ["Ton tour — GX lit vite.", "Draft macro maintenant.", "Bo1 LEC."],
  },
  heretics: {
    intro: [
      "Hatrixx et Heretics — draft imprévisible en Bo1.",
      "bluerzor veut l'early, Jackspektra le bot carry.",
    ],
    thinking: ["bluerzor path…", "Kamiloo mid prep.", "Stend roam setup."],
    ban: ["TH ban surprise.", "On retire ton comfort.", "Ban Heretics style."],
    pick: ["Pick TH — off meta possible.", "Jackspektra angle.", "bluerzor tempo."],
    playerTurn: ["À toi. TH draft vite.", "Montre ta prep LEC.", "On teste ta flex."],
  },
  shifters: {
    intro: [
      "Striker et Shifters — nouveau branding, même exigence LEC.",
      "nuc veut le mid prio, Paduck le bot scaling.",
      "On ne draft pas comme BDS. Nouvelle identité, même ambition.",
    ],
    thinking: ["Boukada jungle…", "nuc hover mid.", "Trymbi setup bot."],
    ban: ["Shifters retire ta wincon.", "Ban propre — pool nuc protégé.", "On lit ta bot lane."],
    pick: ["nuc comfort.", "Paduck carry angle.", "Rooster side lane."],
    playerTurn: ["Ton tour. Shifters s'adaptent.", "Draft LEC 2026.", "Montre-nous ta macro."],
  },
  sk: {
    intro: [
      "Own3r et SK — rebuild en cours, draft agressive.",
      "Wunder veut le top, Skeanz le tempo jungle.",
    ],
    thinking: ["Skeanz path…", "LIDER mid.", "Jactroll bot setup."],
    ban: ["SK ban direct.", "On coupe ta comfort.", "Ban rebuild SK."],
    pick: ["Wunder pool.", "SK pick youth.", "Skeanz tempo."],
    playerTurn: ["À toi. SK cherche la win.", "Draft SK Gaming.", "Bo1 — tout ou rien."],
  },
  navi: {
    intro: [
      "Innaxe et NAVI — première vraie saison LEC.",
      "Poby revient en EMEA, Hans SamD veut le bot prio.",
      "NAVI draft méthodique. On apprend vite.",
    ],
    thinking: ["Rhilech jungle…", "Poby mid prep.", "Parus bot setup."],
    ban: ["NAVI retire ta comfort.", "Ban CIS-LEC hybrid.", "On protège Poby."],
    pick: ["Poby angle.", "Maynter top.", "NAVI signature en construction."],
    playerTurn: ["Ton tour. NAVI observe.", "Montre ta draft LEC.", "On cherche la qualification."],
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
  intro: [
    "Draft importante. Pas de seconde chance.",
    "On a préparé plusieurs plans. Tu vas en voir un.",
  ],
  thinking: ["Réflexion en cours…", "On ajuste le plan…", "Lecture adverse en cours…"],
  ban: ["Ban ciblé.", "On retire ta comfort.", "Ban orienté tempo."],
  pick: ["Pick cohérent avec notre plan.", "Signature équipe.", "Flex possible sur ce pick."],
  playerTurn: ["À toi.", "Montre-nous ta prep.", "Ton tour — on observe."],
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

export function coachPortraitUrl(team: WorldsTeam): string | null {
  return bundledCoachPortraitUrl(team.id, team.coach);
}
