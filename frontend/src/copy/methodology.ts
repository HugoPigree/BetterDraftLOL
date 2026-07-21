export const PREDICT_METHODOLOGY_PRO = {
  title: "Mode PRO — comment est calculée la probabilité ?",
  body:
    "Le modèle combine 50 % de force pro (winrates Oracle's Elixir par champion/rôle, sans fallback soloQ), 40 % d'affinité de composition Meraki, 10 % de bonus/malus de side blue, plus les duos et matchups 2v2 mesurés en pro uniquement. Les données manquantes sont signalées explicitement.",
  disclaimer:
    "Estimation sur données pro uniquement — pas une prédiction garantie du résultat en jeu.",
};

export const HEADLINE_METHODOLOGY_PRO = {
  disclaimer:
    "Synthèse automatique des écarts force pro, affinité Meraki et matchups duo 2v2 mesurés.",
};

export const DUO_SECTION_METHODOLOGY_PRO = {
  body:
    "Scores de synergie interne et matchups 2v2 basés uniquement sur les games pro Oracle's Elixir. Pas d'estimation Meraki ni soloQ en mode PRO.",
};

export const RETROSPECTIVE_BAN_METHODOLOGY_PRO = {
  body:
    "Simule un ban manqué et recalcule la prédiction en mode PRO (données pro + duos mesurés). Justifications sans référence soloQ.",
};

export const RETROSPECTIVE_PICK_METHODOLOGY_PRO = {
  body:
    "Pour l'équipe perdante : alternatives évaluées via le modèle PRO (winrates pro, duos mesurés, affinité Meraki).",
};

export const PRO_TABLE_METHODOLOGY =
  "Winrate pro Oracle's Elixir pour le champion/rôle (minimum 10 games sur les patchs disponibles).";

export const LANE_MATCHUP_METHODOLOGY_PRO =
  "Compare les winrates pro des deux picks sur le même rôle — proxy de lane pro, pas un historique de matchup 1v1.";

export const PREDICT_METHODOLOGY = {
  title: "Comment est calculée la probabilité de victoire ?",
  body:
    "Le modèle combine 50 % de force soloQ (winrates individuels sur le patch), 40 % d'affinité de composition (attributs et archétypes Meraki via XGBoost), 10 % de bonus/malus de side blue, plus les synergies duo internes et les matchups 2v2 jungle-support / bot lane.",
  disclaimer:
    "Estimation statistique sur données soloQ et pro — pas une prédiction garantie du résultat en jeu.",
};

export const HEADLINE_METHODOLOGY = {
  disclaimer:
    "Synthèse automatique des écarts force soloQ, affinité Meraki et matchups duo 2v2.",
};

export const DUO_SECTION_METHODOLOGY = {
  body:
    "Chaque score de synergie interne mesure la complémentarité d'un duo au sein de la même équipe. Les matchups 2v2 comparent les duos face à face. Sources : games pro Oracle's Elixir quand disponibles, sinon estimation soloQ + Meraki.",
};

export const DUO_ADVANTAGE_METHODOLOGY =
  "Écart de winrate 2v2 entre les duos adverses, intégré au calcul global de prédiction.";

export const ARCHETYPE_METHODOLOGY =
  "Tags Meraki agrégés (FIGHTER, MAGE, TANK…) — décrivent la forme de la compo, pas la force brute soloQ.";

export const AFFINITY_METHODOLOGY =
  "Lecture qualitative du profil Meraki moyen (frontline, mobilité, contrôle…) — complète le score ML d'affinité.";

export const SYNTHESIS_METHODOLOGY =
  "Résumé des écarts les plus marquants entre les deux équipes sur les axes du modèle.";

export const LANE_MATCHUP_METHODOLOGY =
  "Compare les winrates soloQ des deux picks sur le même rôle — proxy de lane, pas un vrai historique de matchup.";

export const RETROSPECTIVE_BAN_METHODOLOGY = {
  body:
    "Pour chaque pick adverse, le modèle simule un ban à la place d'un de vos bans actuels, recalcule la prédiction, et retient les bans qui auraient le plus réduit le winrate ennemi (seuil ≥ 0,35 pt). Justifications basées sur soloQ, duos 2v2 et impact modèle.",
};

export const RETROSPECTIVE_PICK_METHODOLOGY = {
  body:
    "Uniquement pour l'équipe perdante : pour chaque rôle, tous les champions disponibles (Meraki) remplacent le pick actuel, puis le modèle recalcule la probabilité de victoire. Le gain affiché = delta en points de winrate estimé.",
};

export const SOLOQ_TABLE_METHODOLOGY =
  "Winrate soloQ EUW du champion sur le rôle assigné pour le patch sélectionné.";
