import { useState, type ReactNode } from "react";
import type { DraftContext, DraftPick } from "../types/draft";
import type { PredictionMode } from "../types/predict";
import type { RoleValidation } from "../utils/autoAssignRoles";
import { BanSlot } from "./BanSlot";
import { ChampionSplashSlot } from "./ChampionSplashSlot";
import { SortablePickColumn } from "./SortablePickColumn";

export type DraftBoardMode = "draft" | "confirmRoles" | "result";

interface ConfirmRolesConfig {
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  blueConfirmed: boolean;
  redConfirmed: boolean;
  blueValidation: RoleValidation;
  redValidation: RoleValidation;
  onBluePicksChange: (picks: DraftPick[]) => void;
  onRedPicksChange: (picks: DraftPick[]) => void;
}

interface DraftBoardProps {
  draft: DraftContext;
  ddragonVersion: string;
  patch: string;
  onPatchChange: (patch: string) => void;
  predictionMode: PredictionMode;
  onPredictionModeChange: (mode: PredictionMode) => void;
  mode?: DraftBoardMode;
  confirmRoles?: ConfirmRolesConfig;
  children?: ReactNode;
}

type PlayerSide = "blue" | "red";

function formatPhase(phase: DraftContext["currentPhase"], mode: DraftBoardMode): string {
  if (mode === "confirmRoles") {
    return "Confirm roles";
  }
  if (mode === "result") {
    return "Draft complete";
  }
  switch (phase) {
    case "ban1":
      return "Ban phase 1";
    case "pick1":
      return "Pick phase 1";
    case "ban2":
      return "Ban phase 2";
    case "pick2":
      return "Pick phase 2";
    case "complete":
      return "Draft complete";
  }
}

function turnLabel(draft: DraftContext, mode: DraftBoardMode): string {
  if (mode === "confirmRoles") {
    return "CONFIRM ROLES";
  }
  if (mode === "result") {
    return "RESULT";
  }
  if (draft.isDraftComplete) {
    return "DRAFT COMPLETE";
  }
  const team = draft.whoseTurn === "blue" ? "BLUE" : "RED";
  const action = draft.currentActionType === "ban" ? "BAN" : "PICK";
  return `${team} ${action}`;
}

function actionHint(draft: DraftContext, isPlayerTurn: boolean, mode: DraftBoardMode): string {
  if (mode === "confirmRoles") {
    return "Glissez les champions pour ajuster les rôles";
  }
  if (mode === "result") {
    return "Analyse terminée";
  }
  if (draft.isDraftComplete) {
    return "Confirmation des rôles…";
  }
  if (!isPlayerTurn) {
    const action = draft.currentActionType === "ban" ? "banning" : "picking";
    return `Opponent is ${action}…`;
  }
  if (draft.currentActionType === "ban") {
    return "Sélectionnez un champion à bannir";
  }
  return "Sélectionnez un champion à pick";
}

function opponentHint(draft: DraftContext, playerSide: PlayerSide): string {
  if (draft.isDraftComplete) {
    return "";
  }
  const opponent = playerSide === "blue" ? "Red" : "Blue";
  const action = draft.currentActionType === "ban" ? "ban" : "pick";
  return `${opponent} Side is ${action}ing…`;
}

export function DraftBoard({
  draft,
  ddragonVersion,
  patch,
  onPatchChange,
  predictionMode,
  onPredictionModeChange,
  mode = "draft",
  confirmRoles,
  children,
}: DraftBoardProps) {
  const [playerSide, setPlayerSide] = useState<PlayerSide>("blue");
  const activeSide = mode === "confirmRoles" ? playerSide : draft.whoseTurn;
  const isPlayerTurn = mode === "draft" && !draft.isDraftComplete && draft.whoseTurn === playerSide;
  const isConfirmMode = mode === "confirmRoles" && Boolean(confirmRoles);

  const blueDisplayPicks = isConfirmMode ? confirmRoles!.bluePicks : draft.bluePicks;
  const redDisplayPicks = isConfirmMode ? confirmRoles!.redPicks : draft.redPicks;

  const currentStep = Math.min(
    draft.actionIndex + (draft.isDraftComplete ? 0 : 1),
    draft.totalActions,
  );
  const progressPct = (draft.actionIndex / draft.totalActions) * 100;
  const activeProgressPct =
    ((draft.actionIndex + (draft.isDraftComplete ? 0 : 0.5)) / draft.totalActions) * 100;
  const progressComplete = mode !== "draft";

  return (
    <div className="drafter">
      <header className="drafter__nav">
        <div className="drafter__progress-wrap" aria-hidden="true">
          <div className="drafter__progress-track">
            <div
              className="drafter__progress-fill"
              style={{ width: `${progressComplete ? 100 : activeProgressPct}%` }}
            />
            <div
              className="drafter__progress-marker"
              style={{ left: `${progressComplete ? 100 : progressPct}%` }}
            />
          </div>
        </div>

        <div className="drafter__nav-row">
          <div className="drafter__nav-left">
            <span className="drafter__nav-label">Navigation</span>
            <span className="drafter__nav-brand">DraftLoL</span>
          </div>

          <div className="drafter__status" key={mode === "draft" ? draft.actionIndex : mode}>
            <span className="drafter__phase drafter__phase-animate">
              {formatPhase(draft.currentPhase, mode)}
            </span>
            <div
              className={[
                "drafter__turn",
                "drafter__turn-animate",
                mode === "confirmRoles" ? "drafter__turn--neutral drafter__turn--confirm" : "",
                mode === "draft" && activeSide ? `drafter__turn--${activeSide}` : "",
                mode === "draft" && !draft.isDraftComplete && activeSide ? "drafter__turn--pulse" : "",
                mode === "result" ? "drafter__turn--done" : "",
              ].join(" ")}
            >
              {turnLabel(draft, mode)}
            </div>
            <span className="drafter__progress">
              {mode === "confirmRoles" ? (
                <>
                  Étape <strong>21</strong> — Confirm roles
                </>
              ) : mode === "result" ? (
                <>Résultat final</>
              ) : (
                <>
                  Action <strong>{currentStep}</strong> / {draft.totalActions}
                </>
              )}
            </span>
          </div>

          <div className="drafter__nav-right">
            <div className="drafter__mode-picker" role="group" aria-label="Mode de prédiction">
              <span className="drafter__mode-picker-label">Mode</span>
              {(["mixed", "pro"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  className={[
                    "drafter__mode-btn",
                    predictionMode === value ? "drafter__mode-btn--active" : "",
                    value === "pro" ? "drafter__mode-btn--pro" : "",
                  ].join(" ")}
                  onClick={() => onPredictionModeChange(value)}
                  aria-pressed={predictionMode === value}
                >
                  {value === "pro" ? "PRO" : "Mixte"}
                </button>
              ))}
            </div>
            {mode === "draft" && (
              <div className="drafter__side-picker" role="group" aria-label="Votre équipe">
                <span className="drafter__side-picker-label">Side</span>
                {(["blue", "red"] as const).map((side) => (
                  <button
                    key={side}
                    type="button"
                    className={[
                      "drafter__side-btn",
                      `drafter__side-btn--${side}`,
                      playerSide === side ? "drafter__side-btn--active" : "",
                    ].join(" ")}
                    onClick={() => setPlayerSide(side)}
                    disabled={draft.isDraftComplete}
                  >
                    {side === "blue" ? "Blue" : "Red"}
                  </button>
                ))}
              </div>
            )}
            {mode === "confirmRoles" && (
              <div className="drafter__side-picker" role="group" aria-label="Équipe à éditer">
                <span className="drafter__side-picker-label">Edit</span>
                {(["blue", "red"] as const).map((side) => (
                  <button
                    key={side}
                    type="button"
                    className={[
                      "drafter__side-btn",
                      `drafter__side-btn--${side}`,
                      playerSide === side ? "drafter__side-btn--active" : "",
                    ].join(" ")}
                    onClick={() => setPlayerSide(side)}
                  >
                    {side === "blue" ? "Blue" : "Red"}
                  </button>
                ))}
              </div>
            )}
            <label className="drafter__patch">
              <span className="drafter__patch-label">Patch</span>
              <input
                type="text"
                className="drafter__patch-input"
                value={patch}
                onChange={(event) => onPatchChange(event.target.value)}
                disabled={mode === "result"}
              />
            </label>
          </div>
        </div>
      </header>

      <div className="drafter__body">
        <aside
          className={[
            "drafter__picks",
            "drafter__picks--blue",
            isConfirmMode ? "drafter__picks--sortable" : "",
            mode === "draft" && activeSide === "blue" ? "drafter__picks--active" : "",
            mode === "confirmRoles" && playerSide === "blue" ? "drafter__picks--active" : "",
            isConfirmMode && confirmRoles!.blueConfirmed ? "drafter__picks--confirmed" : "",
          ].join(" ")}
        >
          {isConfirmMode && blueDisplayPicks.length === 5 ? (
            <SortablePickColumn
              picks={blueDisplayPicks}
              side="blue"
              confirmed={confirmRoles!.blueConfirmed}
              onChange={confirmRoles!.onBluePicksChange}
            />
          ) : (
            Array.from({ length: 5 }, (_, index) => (
              <ChampionSplashSlot
                key={`blue-pick-${index}`}
                pick={blueDisplayPicks[index]}
                side="blue"
                index={index}
              />
            ))
          )}
        </aside>

        <section className="drafter__center">
          <div
            className="drafter__center-inner drafter__center-animate"
            key={mode === "draft" ? draft.actionIndex : mode}
          >
            {children}
          </div>
        </section>

        <aside
          className={[
            "drafter__picks",
            "drafter__picks--red",
            isConfirmMode ? "drafter__picks--sortable" : "",
            mode === "draft" && activeSide === "red" ? "drafter__picks--active" : "",
            mode === "confirmRoles" && playerSide === "red" ? "drafter__picks--active" : "",
            isConfirmMode && confirmRoles!.redConfirmed ? "drafter__picks--confirmed" : "",
          ].join(" ")}
        >
          {isConfirmMode && redDisplayPicks.length === 5 ? (
            <SortablePickColumn
              picks={redDisplayPicks}
              side="red"
              confirmed={confirmRoles!.redConfirmed}
              onChange={confirmRoles!.onRedPicksChange}
            />
          ) : (
            Array.from({ length: 5 }, (_, index) => (
              <ChampionSplashSlot
                key={`red-pick-${index}`}
                pick={redDisplayPicks[index]}
                side="red"
                index={index}
              />
            ))
          )}
        </aside>
      </div>

      <footer className="drafter__footer">
        <div className="drafter__bans drafter__bans--blue">
          {Array.from({ length: 5 }, (_, index) => (
            <BanSlot
              key={`blue-ban-${index}`}
              championName={draft.blueBans[index]}
              version={ddragonVersion}
              side="blue"
              slotIndex={index}
            />
          ))}
        </div>

        <div className="drafter__action">
          <span
            className={[
              "drafter__action-btn",
              mode === "result" ? "drafter__action-btn--done" : "",
              mode === "confirmRoles" ? "drafter__action-btn--confirm" : "",
              mode === "draft" && isPlayerTurn ? `drafter__action-btn--${playerSide}` : "",
              mode === "draft" && isPlayerTurn ? "drafter__action-btn--active" : "",
              mode === "draft" && !draft.isDraftComplete && !isPlayerTurn
                ? "drafter__action-btn--waiting"
                : "",
            ].join(" ")}
          >
            <span className="drafter__action-primary">{actionHint(draft, isPlayerTurn, mode)}</span>
            {mode === "draft" && !draft.isDraftComplete && !isPlayerTurn && (
              <span className="drafter__action-secondary">{opponentHint(draft, playerSide)}</span>
            )}
          </span>
          {mode === "draft" && !draft.isDraftComplete && (
            <button type="button" className="drafter__reset" onClick={draft.resetDraft}>
              Reset draft
            </button>
          )}
        </div>

        <div className="drafter__bans drafter__bans--red">
          {Array.from({ length: 5 }, (_, index) => (
            <BanSlot
              key={`red-ban-${index}`}
              championName={draft.redBans[index]}
              version={ddragonVersion}
              side="red"
              slotIndex={index}
            />
          ))}
        </div>
      </footer>
    </div>
  );
}
