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
  | { type: "bot_ban"; champion: string; reason?: string | null }
  | { type: "bot_pick"; champion: string; role?: Role; reason?: string | null }
  | { type: "player_ban"; champion: string }
  | { type: "player_pick"; champion: string; role?: Role }
  | { type: "player_turn" }
  | { type: "error" }
  | { type: "draft_complete" };

function pickRandom(lines: string[]): string {
  if (lines.length === 0) {
    return "";
  }
  return lines[Math.floor(Math.random() * lines.length)] ?? lines[0];
}

function normalizeChampion(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, "");
}

/** Répliques spécifiques quand un champion rappelle l'ex (40 % de chance si match). */
const EX_CHAMPION_CALLBACKS: Record<string, string[]> = {
  seraphine: [
    "À oe Seraphine… le genre de pick qui chante trop fort en vocal. Ça me rappelle des ex, pas Daisy — elle, c'était pire.",
    "Seraphine ? Ego + ult flashy. J'ai des traumas, mais pas celui-là en particulier.",
    "Pick Seraphine… vibes TikTok concert. Moi j'ai pleuré sur autre chose hier soir.",
  ],
  yuumi: [
    "Yuumi… collante comme Daisy. Impossible de la detach du tab.",
    "Pick Yuumi ? Moi aussi j'ai été le support émotionnel de quelqu'un. Regarde où ça m'a mené.",
  ],
  ahri: [
    "Ahri. Charme, manipulation, tu te barres après. Daisy en foxgirl.",
    "Ahri me donne des flashbacks. Spoiler : j'ai pas survécu au charm.",
  ],
  lux: [
    "Lux… sourire de lumière, cœur en shadow. Tu vois le genre. Daisy.",
    "Lux me rappelle quelqu'un. Trop de poke, pas assez de commit.",
  ],
  ezreal: [
    "Ezreal ? Flashy, ego, dodge les vrais problèmes. Daisy en ADC.",
    "Ezreal… Daisy aussi se croyait irremplaçable. Plot twist : si.",
  ],
  zed: [
    "Zed. Shadows everywhere, feelings nowhere. Breakup speedrun any%",
    "Daisy était un main Zed : présente que quand ça l'arrange.",
  ],
  thresh: [
    "Thresh… tu me hook le cœur puis tu me laisses en lanterne. Classique ex behavior.",
    "Thresh me rappelle Daisy. Toujours une excuse pour pas follow up.",
  ],
  nami: [
    "Nami… vague émotionnelle incoming. Comme le dernier message de Daisy.",
    "Nami bubble ? Moi c'était une bulle de déni pendant six mois.",
  ],
  lulu: [
    "Lulu… Daisy polymorph mes feelings et part en faerie.",
    "Daisy avait l'énergie Lulu : mignonne jusqu'au moment où tu int.",
  ],
  vayne: [
    "Vayne… chasse les méchants sauf elle-même. Très ex-core.",
    "Vayne tumble away from commitment. Je connais trop bien.",
  ],
  kaisa: [
    "Kai'Sa… isolée dans le void comme moi dans ma chambre post-breakup.",
    "Kai'Sa me rappelle Daisy : toujours en mode survie, jamais en mode couple.",
  ],
  sona: [
    "Sona… zéro dialogue, que des vibes. Comme nos derniers mois.",
    "Sona mute ? Daisy aussi arrêtait de répondre du jour au lendemain.",
  ],
  akali: [
    "Akali… disparaît dans la brume quand ça devient sérieux. Ex certified.",
  ],
  yasuo: [
    "Yasuo… 0/10 mental mais il croit encore qu'il carry. Daisy en bcp.",
  ],
  jinx: [
    "Jinx ? Chaos, rires nerveux, puis tout explose. Très breakup energy.",
  ],
};

function maybeExChampionLine(champion: string): string | null {
  const key = normalizeChampion(champion);
  const lines = EX_CHAMPION_CALLBACKS[key];
  if (!lines || lines.length === 0) {
    return null;
  }
  if (Math.random() > 0.42) {
    return null;
  }
  return pickRandom(lines);
}

function withChampionFlavor(
  champion: string,
  genericLines: string[],
  flavoredLines: string[],
): string {
  const exLine = maybeExChampionLine(champion);
  if (exLine) {
    return exLine;
  }
  return pickRandom([...genericLines, ...flavoredLines]);
}

const INTRO_LINES = [
  "Salut. Moi c'est ton rival. Et oui j'ai dumpé Daisy y'a deux semaines, donc je suis en mode tryhard émotionnel.",
  "Draft contre moi ? Ok. J'ai pleuré sur le profil de Daisy hier soir mais aujourd'hui je ban ta win condition.",
  "Prêt ? Moi oui. J'ai fini ma phase de deuil… enfin j'ai dit ça à 3h du mat' en regardant nos anciens matchs.",
  "Tu veux jouer ? Parfait. J'ai besoin de win pour prouver à Daisy que je suis stable. Spoiler : je suis pas stable.",
  "Bienvenue. Le cœur est brisé mais le macro est intact. Enfin j'espère.",
  "On draft ? Cool. J'ai supprimé le main de Daisy du client… enfin j'ai rechute ce matin.",
  "Tu crois que c'est juste un bot ? Non. C'est un mec fraîchement célibataire avec un algo pro et des traumas.",
  "Salut champion. Daisy m'a dit que je draftais mal. Donc là je vais humilier tout le monde par principe.",
  "Mode draft activé. J'ai block le Discord de Daisy mais pas les flashbacks sur certains picks.",
  "Allez, montre ta compo. Moi je montre que j'ai moved on. (J'ai pas moved on.)",
];

const THINKING_BAN_LINES = [
  "Hmm… quel ban va te faire tilt ET me rappeler pourquoi je suis plus avec Daisy ?",
  "Ban phase. Je cherche le pick qui te fait mal… pas celui qui me fait pleurer. Priorités.",
  "Laisse-moi réfléchir. Daisy m'a ghost, moi je ban ton comfort.",
  "Quel champion tu voulais ? Je le vole. Comme Daisy m'a volé ma paix mentale.",
  "Je scanne le pool… et mes traumas. Deuxième passe.",
  "Ban incoming. J'ai appris du breakup : faut viser les dépendances émotionnelles.",
  "Attends, je choisis un ban cruel mais thérapeutique.",
  "Ton one-trick va rester en dehors. Comme moi du cœur de Daisy. Too much ? Non.",
  "Je réfléchis… entre meta pro et petit revenge fantasy sain.",
  "Ban stratégique en cours. Ne pas penser à Daisy. Ne pas penser à Daisy.",
];

const THINKING_PICK_LINES = [
  "Attends, je construis une compo cohérente. Daisy disait que j'étais incohérent. On va voir.",
  "Synergie, winrate, closure émotionnelle… j'optimise tout.",
  "Je sens un pick solide. Pas comme mes choix amoureux récents.",
  "Pick phase. Là je draft avec la tête, pas avec le cœur. Enfin j'essaye.",
  "Je compose une équipe qui a un plan. Contrairement à notre relation.",
  "Calcul pro en cours. J'ignore les flashbacks. J'ignore les flashbacks.",
  "Un pick meta arrive. Mon thérapeute serait fier. Daisy s'en fiche.",
  "Je lock quelque chose de propre. Tu vas voir ce qu'est la stabilité.",
  "Attends… engage, peel, scaling. Pas drama. Pour une fois.",
  "Je cherche le pick qui carry ET qui me donne pas des vibes de couple toxique.",
];

const BOT_BAN_GENERIC = [
  (c: string) => `${c} ? Banni. Tu le toucheras pas. Comme Daisy m'a touché le cœur puis ghost.`,
  (c: string) => `Adieu ${c}. C'était ton win condition ? Dommage. J'ai l'habitude des déceptions.`,
  (c: string) => `${c} reste dehors. Next. J'apprends à fermer des portes.`,
  (c: string) => `Ban ${c}. Tu voulais confort, j'offre du chaos sain.`,
  (c: string) => `${c} ? Non. Je suis allergique aux trucs qui me font trop plaisir.`,
  (c: string) => `${c} ban. Considère ça comme un ex qui te répond enfin. Négativement.`,
  (c: string) => `Out ${c}. Pool fermé. Cœur aussi, mais on draft quand même.`,
  (c: string) => `${c} ne passera pas. Meta pro > sentiments. Enfin cette fois si.`,
  (c: string) => `Je retire ${c}. Tu vas devoir impro. Bienvenue dans ma vie post-breakup.`,
  (c: string) => `${c} ? Banned. Spoiler : le contrôle c'est aussi du healing.`,
];

const BOT_BAN_EX_FLAVOR = [
  (c: string) => `${c} ban. Il me rappelle trop quelqu'un. Next.`,
  (c: string) => `Pas ${c}. J'ai déjà assez de triggers cette semaine.`,
  (c: string) => `${c} dehors. Daisy l'adorait. Donc non.`,
];

const BOT_PICK_GENERIC = [
  (c: string) => `${c}. Propre. Tu suis ou tu rage comme Daisy en ranked ?`,
  (c: string) => `Je lock ${c}. Mes calculs pro ne mentent pas. Elle, si.`,
  (c: string) => `${c}. Ta réaction va être priceless. La mienne aussi, mais c'est autre chose.`,
  (c: string) => `${c}. Comp cohérente. Nouveau moi. Who dis ?`,
  (c: string) => `Pick ${c}. J'ai enfin un plan de jeu. Progress.`,
  (c: string) => `${c}. Solide. Pas de red flag. Enfin si, je suis le bot.`,
  (c: string) => `Je prends ${c}. Tu peux tilt, moi j'ai déjà tilt sur l'amour.`,
  (c: string) => `${c}. Synergie validée. Closure émotionnelle : pending.`,
  (c: string) => `${c}. C'est beau une draft qui a du sens. Contrairement à nos derniers messages.`,
  (c: string) => `Lock ${c}. Meta, synergie, et zéro message à 2h du mat'.`,
];

const BOT_PICK_EX_FLAVOR = [
  (c: string) => `${c}. Ça me rappelle personne. C'est reposant.`,
  (c: string) => `${c}. Pick safe émotionnellement. Enfin.`,
];

const PLAYER_BAN_GENERIC = [
  (c: string) => `Tu ban ${c} ? Cute. J'avais un plan B. Daisy aussi avait un plan B apparemment.`,
  (c: string) => `${c} ban… Ok, tu lis le meta. Impressionnant. Daisy lisait que mes stories.`,
  (c: string) => `Ban ${c}. J'espère que t'as réfléchi deux secondes. Moi j'ai réfléchi des mois trop tard.`,
  (c: string) => `${c} ? Tu me le retires ? Rude. Comme un unfollow sans explication.`,
  (c: string) => `Tu vires ${c}. Strat correcte. Le cœur c'est plus compliqué.`,
  (c: string) => `${c} ban. Tu vises mon confort pick ? Je connais ce feeling.`,
  (c: string) => `Ok ${c} out. Je m'adapte. Growth mindset post-breakup edition.`,
  (c: string) => `${c} banni. Au moins en draft les bans sont clairs. Pas comme les mixed signals.`,
  (c: string) => `Tu ban ${c}. Fine. J'ai appris à pivot. Therapist approved.`,
  (c: string) => `${c} ? Retiré du pool. Dommage. Pas tant que ça.`,
];

const PLAYER_BAN_EX = [
  (c: string) => `Tu ban ${c} ? Moi aussi j'aurais dû ban certains feelings plus tôt.`,
  (c: string) => `${c} ban… ça me trigger pas. Miracle.`,
];

const PLAYER_PICK_WITH_ROLE = [
  (c: string, r: string) => `${c} ${r} ? Intéressant… mauvais, mais intéressant. Comme notre première date.`,
  (c: string, r: string) => `Ah, ${c} en ${r}. Je note pour te punir. Et pour pleurer plus tard. Non je rigole. Si.`,
  (c: string, r: string) => `${c} (${r}). Tu crois que ça suffit ? Daisy croyait aussi.`,
  (c: string, r: string) => `${c} ${r}… bold. J'aime les drafts avec du drama.`,
  (c: string, r: string) => `Tu lock ${c} ${r}. Je respecte l'audace. Pas toujours les résultats.`,
  (c: string, r: string) => `${c} en ${r}. Ok ok. Je prépare la réponse émotionnelle… je veux dire stratégique.`,
  (c: string, r: string) => `${c} ${r}. Tu construis quelque chose ? Moi j'apprends encore.`,
  (c: string, r: string) => `Pick ${c} ${r}. Je vais adapter. Adaptabilité : seule leçon du breakup.`,
  (c: string, r: string) => `${c} (${r}). Tu me testes ? J'ai déjà fail ce QCM en vrai vie.`,
  (c: string, r: string) => `${c} ${r}. Sympa. Pas meta pro mais sympa. Comme les red flags qu'on ignore.`,
];

const PLAYER_PICK_NO_ROLE = [
  (c: string) => `${c} ? Bold pick. J'aime quand c'est facile de te read.`,
  (c: string) => `Tu prends ${c}… courageux. Ou pas. Hard to tell, comme le « je t'aime bien » de Daisy.`,
  (c: string) => `${c}. Ok. Je garde mes remarques pour après. Comme Daisy.`,
  (c: string) => `${c} ? Intriguant. Daisy aussi faisait des choix surprenants. Mauvais, mais surprenants.`,
  (c: string) => `Lock ${c}. On verra. J'ai appris à plus juger trop vite. Enfin j'essaye.`,
  (c: string) => `${c}… tu m'inquiètes pas encore. Give me one more pick.`,
];

const PLAYER_TURN_LINES = [
  "À toi. Essaie de pas int. Daisy intait, regarde où on en est.",
  "Allez, montre-moi ton plus beau pick. Pas ton pire coping mechanism.",
  "Ton tour. Le public attend. Moi j'attends la closure.",
  "Go. Draft vite avant que je repense à des trucs.",
  "À toi champion. Fais un choix assumé. Contrairement à certains.",
  "Ton move. J'ai la patience d'un mec qui scroll encore le profil de Daisy. Enfin non. Go.",
  "Place au joueur. Impressionne-moi. J'ai besoin de bonnes nouvelles aujourd'hui.",
  "C'est ton tour. Meta ou ego ? Les deux c'est Daisy, mais toi tu peux mieux.",
  "À toi. Pick something stable. Trust.",
  "Ton tour. Ne me ghost pas mid-draft, ce serait meta.",
];

const ERROR_LINES = [
  "Même mon cœur a crashé. Recharge l'API, champion.",
  "Erreur technique. Même le serveur refuse cette draft. Comme Daisy avec nos plans du weekend.",
  "Bug ? Non. C'est l'univers qui proteste contre tes picks. Et ma timeline.",
  "Something broke. Pas mes feelings, eux c'est déjà fait.",
  "Erreur. Respire. Reload. Moi je respire depuis deux semaines.",
  "Crash. Draft buguée ou karma ? Les deux probablement.",
  "L'API a tilt. Je la comprends. J'ai tilt aussi récemment.",
  "Problème serveur. On retry ? Les relations c'est pas aussi simple.",
];

const DRAFT_COMPLETE_LINES = [
  "Draft finie. Spoiler : je gagne. Spoiler 2 : j'ai toujours pas texté Daisy.",
  "C'est tout ? Ta compo sent la défaite. La mienne sent le healing arc.",
  "On verra au résultat… mais j'ai déjà gagné mentalement. Partially.",
  "Draft complete. Win or lose, au moins personne m'a ghost ici.",
  "Fin de draft. Belle comp… pour une team. Pas pour une relation. Anyway.",
  "C'est lock. Place au jeu. Là au moins les règles sont claires.",
  "Draft terminée. Que le meilleur win. Et que moi je dorme cette nuit.",
  "On a fini. Ta compo est… intéressante. Comme ma vie récemment.",
  "GG draft phase. Maintenant exécute. Contrairement à moi sur certains callouts.",
  "Draft bouclée. J'ai plus de closure ici qu'en trois mois de situationship.",
];

function mapLines(champion: string, lines: Array<(c: string) => string>): string[] {
  return lines.map((fn) => fn(champion));
}

function mapLinesRole(
  champion: string,
  role: string,
  lines: Array<(c: string, r: string) => string>,
): string[] {
  return lines.map((fn) => fn(champion, role));
}

export function lineForBotEvent(event: BotDialogueEvent): string {
  switch (event.type) {
    case "intro":
      return pickRandom(INTRO_LINES);
    case "thinking":
      return pickRandom(event.action === "ban" ? THINKING_BAN_LINES : THINKING_PICK_LINES);
    case "bot_ban":
      if (event.reason?.trim()) {
        return event.reason.trim();
      }
      return withChampionFlavor(
        event.champion,
        mapLines(event.champion, BOT_BAN_GENERIC),
        mapLines(event.champion, BOT_BAN_EX_FLAVOR),
      );
    case "bot_pick": {
      if (event.reason?.trim()) {
        return event.reason.trim();
      }
      const exLine = maybeExChampionLine(event.champion);
      if (exLine) {
        return exLine;
      }
      return pickRandom([
        ...mapLines(event.champion, BOT_PICK_GENERIC),
        ...mapLines(event.champion, BOT_PICK_EX_FLAVOR),
      ]);
    }
    case "player_ban":
      return withChampionFlavor(
        event.champion,
        mapLines(event.champion, PLAYER_BAN_GENERIC),
        mapLines(event.champion, PLAYER_BAN_EX),
      );
    case "player_pick":
      if (event.role) {
        const role = ROLE_FR[event.role];
        const exLine = maybeExChampionLine(event.champion);
        if (exLine) {
          return exLine;
        }
        return pickRandom(mapLinesRole(event.champion, role, PLAYER_PICK_WITH_ROLE));
      }
      return withChampionFlavor(
        event.champion,
        mapLines(event.champion, PLAYER_PICK_NO_ROLE),
        [],
      );
    case "player_turn":
      return pickRandom(PLAYER_TURN_LINES);
    case "error":
      return pickRandom(ERROR_LINES);
    case "draft_complete":
      return pickRandom(DRAFT_COMPLETE_LINES);
  }
}

export function botSideForPlayer(playerSide: Team): Team {
  return playerSide === "blue" ? "red" : "blue";
}
