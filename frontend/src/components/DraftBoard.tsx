import { type ReactNode } from "react";
import type { DraftContext, DraftPick, Team } from "../types/draft";
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

interface EditCompConfig {
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  onBluePicksChange: (picks: DraftPick[]) => void;
  onRedPicksChange: (picks: DraftPick[]) => void;
  onSlotEdit: (side: Team, slotIndex: number) => void;
  selectedSlot: { side: Team; slotIndex: number } | null;
}

interface DraftBoardProps {
  draft: DraftContext;
  ddragonVersion: string;
  patch: string;
  onPatchChange: (patch: string) => void;
  predictionMode: PredictionMode;
  onPredictionModeChange: (mode: PredictionMode) => void;
  playerSide: Team;
  onPlayerSideChange: (side: Team) => void;
  botEnabled: boolean;
  onBotEnabledChange: (enabled: boolean) => void;
  botThinking?: boolean;
  botError?: string | null;
  mode?: DraftBoardMode;
  confirmRoles?: ConfirmRolesConfig;
  editComp?: EditCompConfig;
  highlightedChampion?: string | null;
  highlightedSide?: Team | null;
  resultBluePicks?: DraftPick[];
  resultRedPicks?: DraftPick[];
  children?: ReactNode;
}

type PlayerSide = Team;

function formatPhase(phase: DraftContext["currentPhase"], mode: DraftBoardMode, isEditing: boolean): string {
  if (isEditing) {
    return "Edit comp";
  }
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

function turnLabel(draft: DraftContext, mode: DraftBoardMode, isEditing: boolean): string {
  if (isEditing) {
    return "EDIT COMP";
  }
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

function actionHint(
  draft: DraftContext,
  isPlayerTurn: boolean,
  mode: DraftBoardMode,
  isEditing: boolean,
  botThinking: boolean,
  botEnabled: boolean,
): string {
  if (isEditing) {
    return "Glissez pour les rôles · Changer pour remplacer un pick";
  }
  if (mode === "confirmRoles") {
    return "Glissez les champions pour ajuster les rôles";
  }
  if (mode === "result") {
    return isEditing ? "Modification en cours…" : "Analyse terminée";
  }
  if (draft.isDraftComplete) {
    return "Confirmation des rôles…";
  }
  if (!isPlayerTurn) {
    if (botEnabled && botThinking) {
      const action = draft.currentActionType === "ban" ? "ban" : "pick";
      return `Bot en réflexion (${action})…`;
    }
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
  playerSide,
  onPlayerSideChange,
  botEnabled,
  onBotEnabledChange,
  botThinking = false,
  botError = null,
  mode = "draft",
  confirmRoles,
  editComp,
  highlightedChampion = null,
  highlightedSide = null,
  resultBluePicks,
  resultRedPicks,
  children,
}: DraftBoardProps) {
  const isEditMode = mode === "result" && Boolean(editComp);
  const activeSide = mode === "confirmRoles" || isEditMode ? playerSide : draft.whoseTurn;
  const isPlayerTurn = mode === "draft" && !draft.isDraftComplete && draft.whoseTurn === playerSide;
  const isConfirmMode = mode === "confirmRoles" && Boolean(confirmRoles);
  const explaining = Boolean(highlightedChampion && highlightedSide);

  function slotHighlight(side: Team, pick?: { champion: string }) {
    if (!explaining || !pick) {
      return { highlighted: false, dimmed: false };
    }
    if (side !== highlightedSide) {
      return { highlighted: false, dimmed: true };
    }
    const match = pick.champion.toLowerCase() === highlightedChampion!.toLowerCase();
    return { highlighted: match, dimmed: !match };
  }

  const blueDisplayPicks = isEditMode
    ? editComp!.bluePicks
    : isConfirmMode
      ? confirmRoles!.bluePicks
      : mode === "result" && resultBluePicks
        ? resultBluePicks
        : draft.bluePicks;
  const redDisplayPicks = isEditMode
    ? editComp!.redPicks
    : isConfirmMode
      ? confirmRoles!.redPicks
      : mode === "result" && resultRedPicks
        ? resultRedPicks
        : draft.redPicks;

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
              {formatPhase(draft.currentPhase, mode, isEditMode)}
            </span>
            <div
              className={[
                "drafter__turn",
                "drafter__turn-animate",
                mode === "confirmRoles" ? "drafter__turn--neutral drafter__turn--confirm" : "",
                isEditMode ? "drafter__turn--neutral drafter__turn--confirm" : "",
                mode === "draft" && activeSide ? `drafter__turn--${activeSide}` : "",
                mode === "draft" && !draft.isDraftComplete && activeSide ? "drafter__turn--pulse" : "",
                mode === "result" ? "drafter__turn--done" : "",
              ].join(" ")}
            >
              {turnLabel(draft, mode, isEditMode)}
            </div>
            <span className="drafter__progress">
              {mode === "confirmRoles" ? (
                <>
                  Étape <strong>21</strong> — Confirm roles
                </>
              ) : mode === "result" ? (
                <>{isEditMode ? "Modification de la compo" : "Résultat final"}</>
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
              <>
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
                      onClick={() => onPlayerSideChange(side)}
                      disabled={draft.isDraftComplete}
                    >
                      {side === "blue" ? "Blue" : "Red"}
                    </button>
                  ))}
                </div>
                <div className="drafter__side-picker" role="group" aria-label="Adversaire">
                  <span className="drafter__side-picker-label">Bot PRO</span>
                  <button
                    type="button"
                    className={[
                      "drafter__mode-btn",
                      "drafter__mode-btn--pro",
                      botEnabled ? "drafter__mode-btn--active" : "",
                    ].join(" ")}
                    onClick={() => onBotEnabledChange(!botEnabled)}
                    disabled={draft.isDraftComplete}
                    aria-pressed={botEnabled}
                    title="Adversaire basé uniquement sur les données pro"
                  >
                    {botEnabled ? "ON" : "OFF"}
                  </button>
                </div>
              </>
            )}
            {(mode === "confirmRoles" || isEditMode) && (
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
                    onClick={() => onPlayerSideChange(side)}
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
                disabled={mode === "result" && !isEditMode}
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
            isConfirmMode || isEditMode ? "drafter__picks--sortable" : "",
            mode === "draft" && activeSide === "blue" ? "drafter__picks--active" : "",
            (mode === "confirmRoles" || isEditMode) && playerSide === "blue"
              ? "drafter__picks--active"
              : "",
            isConfirmMode && confirmRoles!.blueConfirmed ? "drafter__picks--confirmed" : "",
          ].join(" ")}
        >
          {(isConfirmMode || isEditMode) && blueDisplayPicks.length === 5 ? (
            <SortablePickColumn
              picks={blueDisplayPicks}
              side="blue"
              confirmed={isConfirmMode ? confirmRoles!.blueConfirmed : false}
              onChange={
                isEditMode ? editComp!.onBluePicksChange : confirmRoles!.onBluePicksChange
              }
              editable={isEditMode}
              selectedSlotIndex={
                isEditMode && editComp!.selectedSlot?.side === "blue"
                  ? editComp!.selectedSlot.slotIndex
                  : null
              }
              onSlotEdit={
                isEditMode ? (slotIndex) => editComp!.onSlotEdit("blue", slotIndex) : undefined
              }
              highlightedChampion={highlightedSide === "blue" ? highlightedChampion : null}
              dimUnhighlighted={explaining}
            />
          ) : (
            Array.from({ length: 5 }, (_, index) => {
              const pick = blueDisplayPicks[index];
              const hl = slotHighlight("blue", pick);
              return (
                <ChampionSplashSlot
                  key={`blue-pick-${index}`}
                  pick={pick}
                  side="blue"
                  index={index}
                  highlighted={hl.highlighted}
                  dimmed={hl.dimmed}
                />
              );
            })
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
            isConfirmMode || isEditMode ? "drafter__picks--sortable" : "",
            mode === "draft" && activeSide === "red" ? "drafter__picks--active" : "",
            (mode === "confirmRoles" || isEditMode) && playerSide === "red"
              ? "drafter__picks--active"
              : "",
            isConfirmMode && confirmRoles!.redConfirmed ? "drafter__picks--confirmed" : "",
          ].join(" ")}
        >
          {(isConfirmMode || isEditMode) && redDisplayPicks.length === 5 ? (
            <SortablePickColumn
              picks={redDisplayPicks}
              side="red"
              confirmed={isConfirmMode ? confirmRoles!.redConfirmed : false}
              onChange={
                isEditMode ? editComp!.onRedPicksChange : confirmRoles!.onRedPicksChange
              }
              editable={isEditMode}
              selectedSlotIndex={
                isEditMode && editComp!.selectedSlot?.side === "red"
                  ? editComp!.selectedSlot.slotIndex
                  : null
              }
              onSlotEdit={
                isEditMode ? (slotIndex) => editComp!.onSlotEdit("red", slotIndex) : undefined
              }
              highlightedChampion={highlightedSide === "red" ? highlightedChampion : null}
              dimUnhighlighted={explaining}
            />
          ) : (
            Array.from({ length: 5 }, (_, index) => {
              const pick = redDisplayPicks[index];
              const hl = slotHighlight("red", pick);
              return (
                <ChampionSplashSlot
                  key={`red-pick-${index}`}
                  pick={pick}
                  side="red"
                  index={index}
                  highlighted={hl.highlighted}
                  dimmed={hl.dimmed}
                />
              );
            })
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
            <span className="drafter__action-primary">
              {actionHint(draft, isPlayerTurn, mode, isEditMode, botThinking, botEnabled)}
            </span>
            {mode === "draft" && !draft.isDraftComplete && !isPlayerTurn && (
              <span className="drafter__action-secondary">
                {botError ?? opponentHint(draft, playerSide)}
              </span>
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
