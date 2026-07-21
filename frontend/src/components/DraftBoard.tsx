import type { ReactNode } from "react";
import type { DraftContext } from "../types/draft";
import { ChampionIcon } from "./ChampionIcon";
import { ChampionSplashSlot } from "./ChampionSplashSlot";

interface DraftBoardProps {
  draft: DraftContext;
  ddragonVersion: string;
  children?: ReactNode;
}

function formatPhase(phase: DraftContext["currentPhase"]): string {
  switch (phase) {
    case "ban1":
      return "BAN PHASE 1";
    case "pick1":
      return "PICK PHASE 1";
    case "ban2":
      return "BAN PHASE 2";
    case "pick2":
      return "PICK PHASE 2";
    case "complete":
      return "DRAFT COMPLETE";
  }
}

function turnLabel(draft: DraftContext): string {
  if (draft.isDraftComplete) {
    return "DRAFT COMPLETE";
  }
  const team = draft.whoseTurn === "blue" ? "BLUE" : "RED";
  const action = draft.currentActionType === "ban" ? "BAN" : "PICK";
  return `${team} ${action}`;
}

function waitingLabel(draft: DraftContext): string {
  if (draft.isDraftComplete) {
    return "Analyse en cours";
  }
  if (draft.currentActionType === "ban") {
    return draft.whoseTurn === "blue" ? "Waiting for blue ban" : "Waiting for red ban";
  }
  return draft.whoseTurn === "blue" ? "Waiting for blue pick" : "Waiting for red pick";
}

export function DraftBoard({ draft, ddragonVersion, children }: DraftBoardProps) {
  const activeSide = draft.whoseTurn;

  return (
    <div className="drafter">
      <header className="drafter__nav">
        <div className="drafter__team drafter__team--blue">
          <span className="drafter__team-dot" />
          <span className="drafter__team-name">Blue Side</span>
        </div>

        <div className="drafter__status">
          <span className="drafter__phase">{formatPhase(draft.currentPhase)}</span>
          <div
            className={`drafter__turn ${
              activeSide ? `drafter__turn--${activeSide}` : "drafter__turn--neutral"
            }`}
          >
            {turnLabel(draft)}
          </div>
          <span className="drafter__progress">
            {Math.min(draft.actionIndex + (draft.isDraftComplete ? 0 : 1), draft.totalActions)} /{" "}
            {draft.totalActions}
          </span>
        </div>

        <div className="drafter__team drafter__team--red">
          <span className="drafter__team-name">Red Side</span>
          <span className="drafter__team-dot" />
        </div>
      </header>

      <div className="drafter__body">
        <aside
          className={`drafter__picks drafter__picks--blue ${
            activeSide === "blue" ? "drafter__picks--active" : ""
          }`}
        >
          {Array.from({ length: 5 }, (_, index) => (
            <ChampionSplashSlot
              key={`blue-pick-${index}`}
              pick={draft.bluePicks[index]}
              side="blue"
              index={index}
            />
          ))}
        </aside>

        <section className="drafter__center">{children}</section>

        <aside
          className={`drafter__picks drafter__picks--red ${
            activeSide === "red" ? "drafter__picks--active" : ""
          }`}
        >
          {Array.from({ length: 5 }, (_, index) => (
            <ChampionSplashSlot
              key={`red-pick-${index}`}
              pick={draft.redPicks[index]}
              side="red"
              index={index}
            />
          ))}
        </aside>
      </div>

      <footer className="drafter__footer">
        <div className="drafter__bans drafter__bans--blue">
          {Array.from({ length: 5 }, (_, index) => (
            <ChampionIcon
              key={`blue-ban-${index}`}
              championName={draft.blueBans[index]}
              version={ddragonVersion}
              size={48}
              variant="ban"
              side="blue"
              overlay={draft.blueBans[index] ? "ban" : "none"}
            />
          ))}
        </div>

        <div className="drafter__action">
          <span
            className={`drafter__action-btn ${
              activeSide ? `drafter__action-btn--${activeSide}` : ""
            } ${draft.isDraftComplete ? "drafter__action-btn--done" : ""}`}
          >
            {waitingLabel(draft)}
          </span>
          {!draft.isDraftComplete && (
            <button type="button" className="drafter__reset" onClick={draft.resetDraft}>
              Reset draft
            </button>
          )}
        </div>

        <div className="drafter__bans drafter__bans--red">
          {Array.from({ length: 5 }, (_, index) => (
            <ChampionIcon
              key={`red-ban-${index}`}
              championName={draft.redBans[index]}
              version={ddragonVersion}
              size={48}
              variant="ban"
              side="red"
              overlay={draft.redBans[index] ? "ban" : "none"}
            />
          ))}
        </div>
      </footer>
    </div>
  );
}
