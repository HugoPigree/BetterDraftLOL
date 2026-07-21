import type { DuoMatchupDetail } from "../types/predict";
import {
  averageDuoAttributes,
  resolveMerakiChampionProfile,
  type MerakiAttribute,
  type MerakiChampionCatalog,
} from "./merakiFeatures";

export type DuoMatchupKind = "bot_lane" | "jungle_support";

export interface MatchupExplanation {
  title: string;
  body: string;
  disclaimer: string;
}

const ATTRIBUTE_THRESHOLD = 0.35;
const POKE_DAMAGE_MIN = 2.2;
const POKE_MOBILITY_MAX = 1.6;
const EVEN_WINRATE_MARGIN = 0.025;

interface RuleCandidate {
  priority: number;
  phrase: string;
}

function sideLabel(side: "blue" | "red"): string {
  return side === "blue" ? "Blue Side" : "Red Side";
}

function strongerSideFromMatchup(matchup: DuoMatchupDetail): "blue" | "red" | "even" {
  if (matchup.insufficient_data || matchup.blue_win_probability === null) {
    return "even";
  }
  const margin = Math.abs(matchup.blue_win_probability - 0.5);
  if (margin < EVEN_WINRATE_MARGIN) {
    return "even";
  }
  return matchup.blue_win_probability > 0.5 ? "blue" : "red";
}

function hasPokeProfile(championName: string, catalog: MerakiChampionCatalog): boolean {
  const profile = resolveMerakiChampionProfile(championName, catalog);
  if (!profile) {
    return false;
  }

  const { damage, mobility } = profile.attributeRatings;
  const hasArtillery = profile.roles.includes("ARTILLERY");
  return hasArtillery || (damage >= POKE_DAMAGE_MIN && mobility <= POKE_MOBILITY_MAX);
}

function attributeDelta(
  stronger: Record<MerakiAttribute, number>,
  weaker: Record<MerakiAttribute, number>,
  attribute: MerakiAttribute,
): number {
  return stronger[attribute] - weaker[attribute];
}

function collectAttributeRules(
  strongerAttrs: Record<MerakiAttribute, number>,
  weakerAttrs: Record<MerakiAttribute, number>,
): RuleCandidate[] {
  const rules: RuleCandidate[] = [];

  const mobilityDelta = attributeDelta(strongerAttrs, weakerAttrs, "mobility");
  if (mobilityDelta >= ATTRIBUTE_THRESHOLD) {
    rules.push({
      priority: mobilityDelta,
      phrase:
        "un profil plus mobile, capable d'esquiver l'engage adverse ou de resélectionner les trades",
    });
  }

  const controlDelta = attributeDelta(strongerAttrs, weakerAttrs, "control");
  if (controlDelta >= ATTRIBUTE_THRESHOLD) {
    rules.push({
      priority: controlDelta,
      phrase:
        "davantage d'outils de contrôle de foule pour verrouiller un adversaire en trade ou en pick",
    });
  }

  const toughnessDelta = attributeDelta(strongerAttrs, weakerAttrs, "toughness");
  if (toughnessDelta >= ATTRIBUTE_THRESHOLD) {
    rules.push({
      priority: toughnessDelta,
      phrase: "plus résistant, capable de s'engager dans des trades prolongés sans risque",
    });
  }

  return rules;
}

function collectPokeRule(
  strongerChampions: string[],
  catalog: MerakiChampionCatalog,
): RuleCandidate | null {
  const pokeChampion = strongerChampions.find((champion) => hasPokeProfile(champion, catalog));
  if (!pokeChampion) {
    return null;
  }

  const profile = resolveMerakiChampionProfile(pokeChampion, catalog);
  if (!profile) {
    return null;
  }

  const pokeScore =
    profile.attributeRatings.damage -
    profile.attributeRatings.mobility +
    (profile.roles.includes("ARTILLERY") ? 0.5 : 0);

  return {
    priority: pokeScore,
    phrase:
      "un profil poke à distance, cherchant à infliger des dégâts avant le contact plutôt qu'en mêlée",
  };
}

function composeBody(side: "blue" | "red", phrases: string[]): string {
  const label = sideLabel(side);
  if (phrases.length === 0) {
    return `${label} présente un profil Meraki légèrement plus adapté à ce 2v2, sans avantage net sur un seul axe.`;
  }
  if (phrases.length === 1) {
    return `${label} présente ${phrases[0]}.`;
  }
  return `${label} présente ${phrases[0]}, et ${phrases[1]}.`;
}

function contextHint(kind: DuoMatchupKind): string {
  return kind === "bot_lane" ? "En bot lane" : "En jungle-support";
}

export function generateMatchupExplanation(
  matchup: DuoMatchupDetail,
  kind: DuoMatchupKind,
  catalog: MerakiChampionCatalog,
): MatchupExplanation | null {
  if (matchup.blue_champions.length < 2 || matchup.red_champions.length < 2) {
    return null;
  }

  const blueAttrs = averageDuoAttributes(matchup.blue_champions, catalog);
  const redAttrs = averageDuoAttributes(matchup.red_champions, catalog);
  if (!blueAttrs || !redAttrs) {
    return null;
  }

  const lean = strongerSideFromMatchup(matchup);
  const disclaimer =
    "(analyse basée sur le profil des champions, pas un vrai historique de matchup en jeu)";

  if (lean === "even") {
    return {
      title: "Pourquoi ce matchup penche de ce côté",
      body: `${contextHint(kind)}, les profils Meraki des deux duos restent très proches ; l'écart estimé reste marginal.`,
      disclaimer,
    };
  }

  const strongerChampions = lean === "blue" ? matchup.blue_champions : matchup.red_champions;
  const strongerAttrs = lean === "blue" ? blueAttrs : redAttrs;
  const weakerAttrs = lean === "blue" ? redAttrs : blueAttrs;

  const candidates = collectAttributeRules(strongerAttrs, weakerAttrs);
  const pokeRule = collectPokeRule(strongerChampions, catalog);
  if (pokeRule) {
    candidates.push(pokeRule);
  }

  candidates.sort((a, b) => b.priority - a.priority);
  const topPhrases = candidates.slice(0, 2).map((rule) => rule.phrase);

  return {
    title: "Pourquoi ce matchup penche de ce côté",
    body: composeBody(lean, topPhrases),
    disclaimer,
  };
}
