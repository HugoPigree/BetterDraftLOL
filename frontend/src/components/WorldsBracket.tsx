import type { BracketMatch, WorldsRound, WorldsTeam } from "../types/worlds";
import { WorldsBrand } from "./WorldsBrand";
import {
  bracketById,
  displayTeamName,
  getMatchesByRound,
  getPlayerNextMatch,
  hydrateBracket,
  isSlotLocked,
  shouldRevealRound,
} from "../utils/worldsBracket";

interface WorldsBracketProps {
  playerTeam: WorldsTeam;
  bracket: BracketMatch[];
  onBack: () => void;
  onPlayNextMatch: () => void;
}

function TreeMatch({
  match,
  playerTeamId,
  byId,
}: {
  match: BracketMatch;
  playerTeamId: string;
  byId: Record<string, BracketMatch>;
}) {
  const nameA = displayTeamName(match.team_a, byId);
  const nameB = displayTeamName(match.team_b, byId);
  const lockedA = isSlotLocked(match.team_a, byId);
  const lockedB = isSlotLocked(match.team_b, byId);
  const isPlayer =
    match.team_a.team?.id === playerTeamId || match.team_b.team?.id === playerTeamId;
  const winnerA = match.winner_id && match.team_a.team?.id === match.winner_id;
  const winnerB = match.winner_id && match.team_b.team?.id === match.winner_id;

  return (
    <div
      className={[
        "bracket-tree__match",
        isPlayer ? "bracket-tree__match--player" : "",
        match.winner_id ? "bracket-tree__match--done" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div
        className={[
          "bracket-tree__slot",
          winnerA ? "bracket-tree__slot--winner" : "",
          lockedA ? "bracket-tree__slot--tbd" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {nameA}
      </div>
      <div
        className={[
          "bracket-tree__slot",
          winnerB ? "bracket-tree__slot--winner" : "",
          lockedB ? "bracket-tree__slot--tbd" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {nameB}
      </div>
    </div>
  );
}

function RoundColumn({
  label,
  round,
  bracket,
  playerTeamId,
  visible,
}: {
  label: string;
  round: WorldsRound;
  bracket: BracketMatch[];
  playerTeamId: string;
  visible: boolean;
}) {
  const byId = bracketById(bracket);
  const matches = getMatchesByRound(bracket, round);

  return (
    <div
      className={[
        "bracket-tree__round",
        visible ? "" : "bracket-tree__round--hidden",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span className="bracket-tree__round-label">{label}</span>
      <div className={`bracket-tree__round-matches bracket-tree__round-matches--${round}`}>
        {matches.map((match) => (
          <TreeMatch key={match.id} match={match} playerTeamId={playerTeamId} byId={byId} />
        ))}
      </div>
    </div>
  );
}

export function WorldsBracket({
  playerTeam,
  bracket,
  onBack,
  onPlayNextMatch,
}: WorldsBracketProps) {
  const hydrated = hydrateBracket(bracket);
  const nextMatch = getPlayerNextMatch(hydrated, playerTeam.id);
  const showSemi = shouldRevealRound(hydrated, playerTeam.id, "semi");
  const showFinal = shouldRevealRound(hydrated, playerTeam.id, "final");

  return (
    <div className="worlds-screen worlds-screen--bracket">
      <header className="worlds-screen__header worlds-screen__header--brand">
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={onBack}>
          Accueil
        </button>
        <div className="worlds-screen__header-main">
          <WorldsBrand size="md" subtitle="Bracket à 8" />
          <h1 className="worlds-screen__title">{playerTeam.name}</h1>
          <p className="worlds-screen__subtitle">Coach {playerTeam.coach}</p>
        </div>
      </header>

      <div className="bracket-tree">
        <RoundColumn
          label="Quarts"
          round="quarter"
          bracket={hydrated}
          playerTeamId={playerTeam.id}
          visible
        />
        <div className="bracket-tree__connector" aria-hidden="true" />
        <RoundColumn
          label="Demis"
          round="semi"
          bracket={hydrated}
          playerTeamId={playerTeam.id}
          visible={showSemi}
        />
        <div className="bracket-tree__connector" aria-hidden="true" />
        <RoundColumn
          label="Finale"
          round="final"
          bracket={hydrated}
          playerTeamId={playerTeam.id}
          visible={showFinal}
        />
      </div>

      {nextMatch ? (
        <button type="button" className="worlds-btn worlds-btn--primary" onClick={onPlayNextMatch}>
          Jouer {nextMatch.round_label.toLowerCase()} vs{" "}
          {(() => {
            const byId = bracketById(hydrated);
            const m = hydrated.find((item) => item.id === nextMatch.id)!;
            const isA = m.team_a.team?.id === playerTeam.id;
            return isA
              ? displayTeamName(m.team_b, byId)
              : displayTeamName(m.team_a, byId);
          })()}
        </button>
      ) : (
        <p className="worlds-screen__subtitle">Termine ton match pour débloquer la suite du bracket.</p>
      )}
    </div>
  );
}
