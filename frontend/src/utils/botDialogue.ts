import type { Role, Team } from "../types/draft";

const ROLE_FR: Record<Role, string> = {
  TOP: "top",
  JUNGLE: "jungle",
  MIDDLE: "mid",
  BOTTOM: "adc",
  UTILITY: "support",
};

export type BotDialogueEvent =
  | { type: "intro" }
  | { type: "thinking"; action: "ban" | "pick" }
  | { type: "bot_ban"; champion: string }
  | { type: "bot_pick"; champion: string; role: Role }
  | { type: "player_ban"; champion: string }
  | { type: "player_pick"; champion: string; role?: Role }
  | { type: "player_turn" }
  | { type: "error" }
  | { type: "draft_complete" };

function pickRandom(lines: string[]): string {
  return lines[Math.floor(Math.random() * lines.length)] ?? lines[0] ?? "";
}

function modeFlavor(): string {
  return "Mes calculs pro ne mentent pas.";
}

export function lineForBotEvent(event: BotDialogueEvent): string {
  switch (event.type) {
    case "intro":
      return pickRandom([
        "Salut. Moi c'est ton pire cauchemar en draft. Prêt à perdre ?",
        "Tu veux jouer contre moi ? Ok. Prépare-toi à regretter tes picks.",
        "DraftLoL, mode humiliant activé. Montre-moi ta compo… si tu oses.",
      ]);
    case "thinking":
      return event.action === "ban"
        ? pickRandom([
            "Hmm… quel ban va te faire tilt le plus vite ?",
            "Laisse-moi choisir ce que tu voulais pick. C'est marrant.",
            "Ban phase. Spoiler : tu vas pas aimer.",
          ])
        : pickRandom([
            "Attends, je construis une compo qui te fait mal.",
            "Synergie, winrate, ego… j'optimise tout.",
            "Je sens un pick free win. Tu vas voir.",
          ]);
    case "bot_ban":
      return pickRandom([
        `${event.champion} ? Banni. Tu le toucheras pas. ${modeFlavor()}`,
        `Adieu ${event.champion}. C'était ton win condition, non ?`,
        `${event.champion} reste en dehors. Next.`,
      ]);
    case "bot_pick":
      return pickRandom([
        `${event.champion} en ${ROLE_FR[event.role]}. Propre. Tu suis ou tu rage ?`,
        `Je lock ${event.champion} ${ROLE_FR[event.role]}. ${modeFlavor()}`,
        `${event.champion} (${ROLE_FR[event.role]}). Ta réaction va être priceless.`,
      ]);
    case "player_ban":
      return pickRandom([
        `Tu ban ${event.champion} ? Cute. J'avais un plan B anyway.`,
        `${event.champion} ban… Ok, tu lis Reddit. Impressionnant.`,
        `Ban ${event.champion}. J'espère que t'as réfléchi deux secondes.`,
      ]);
    case "player_pick":
      return event.role
        ? pickRandom([
            `${event.champion} ${ROLE_FR[event.role]} ? Intéressant… mauvais, mais intéressant.`,
            `Ah, ${event.champion} en ${ROLE_FR[event.role]}. Je note pour te punir plus tard.`,
            `${event.champion} (${ROLE_FR[event.role]}). Tu crois vraiment que ça suffit ?`,
          ])
        : pickRandom([
            `${event.champion} ? Bold pick. J'aime quand c'est facile.`,
            `Tu prends ${event.champion}… courageux. Ou pas.`,
          ]);
    case "player_turn":
      return pickRandom([
        "À toi. Essaie de pas int.",
        "Allez, montre-moi ton plus beau throw.",
        "Ton tour. Le public attend une erreur.",
      ]);
    case "error":
      return pickRandom([
        "Même mon cerveau a crashé. Recharge l'API, champion.",
        "Erreur technique. Même le serveur refuse ta draft.",
        "Bug ? Non. C'est l'univers qui proteste contre tes picks.",
      ]);
    case "draft_complete":
      return pickRandom([
        "Draft finie. Spoiler : je gagne.",
        "C'est tout ? Ta compo sent la défaite.",
        "On verra au résultat… mais j'ai déjà gagné mentalement.",
      ]);
  }
}

export function botSideForPlayer(playerSide: Team): Team {
  return playerSide === "blue" ? "red" : "blue";
}
