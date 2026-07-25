import { useEffect, useRef, useState } from "react";
import type { Role, Team } from "../types/draft";
import type { PredictionMode } from "../types/predict";
import { BotVisualNovel } from "./BotVisualNovel";
import { ChampionGrid } from "./ChampionGrid";
import { ConfirmRolesPhase } from "./ConfirmRolesPhase";
import { DraftBoard } from "./DraftBoard";
import { DraftResult } from "./DraftResult";
import { EditCompPhase } from "./EditCompPhase";
import { useBotDialogue } from "../hooks/useBotDialogue";
import { useBotExplanation } from "../hooks/useBotExplanation";
import { useDraftBot } from "../hooks/useDraftBot";
import { useDraftState } from "../hooks/useDraftState";
import { formatMetaStatusLabel, useMetaStatus } from "../hooks/useMetaStatus";
import { usePostDraftFlow } from "../hooks/usePostDraftFlow";
import { fetchChampionsFromApi } from "../services/api";
import { fetchLatestDdragonVersion } from "../utils/ddragon";

interface DraftVsBotAppProps {
  onBack: () => void;
}

export function DraftVsBotApp({ onBack }: DraftVsBotAppProps) {
  const draft = useDraftState();
  const [champions, setChampions] = useState<string[]>([]);
  const [championPositions, setChampionPositions] = useState<Record<string, Role[]>>({});
  const [estimatedChampions, setEstimatedChampions] = useState<string[]>([]);
  const [ddragonVersion, setDdragonVersion] = useState("14.23.1");
  const [patch, setPatch] = useState("16.13");
  const patchInitializedRef = useRef(false);
  const { status: metaStatus } = useMetaStatus();
  const [predictionMode, setPredictionMode] = useState<PredictionMode>("mixed");
  const [playerSide, setPlayerSide] = useState<Team>("blue");
  const [botEnabled, setBotEnabled] = useState(true);
  const [loadingChampions, setLoadingChampions] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const postDraft = usePostDraftFlow(draft, championPositions);
  const { thinking: botThinking, error: botError, lastMove: botLastMove } = useDraftBot({
    enabled: botEnabled && postDraft.phase === "drafting",
    draft,
    playerSide,
    champions,
    patch,
  });

  const botDialogue = useBotDialogue({
    enabled: botEnabled && postDraft.phase === "drafting",
    draft,
    playerSide,
    botThinking,
    botError,
    lastBotMove: botLastMove,
  });

  const botSide: Team = playerSide === "blue" ? "red" : "blue";
  const botPicks = botSide === "blue" ? postDraft.bluePicks : postDraft.redPicks;
  const opponentPicks = botSide === "blue" ? postDraft.redPicks : postDraft.bluePicks;

  const botExplanation = useBotExplanation({
    botSide,
    botPicks,
    opponentPicks,
    patch,
    mode: "pro",
    enabled: botEnabled && postDraft.phase === "result" && !postDraft.isEditing,
  });

  useEffect(() => {
    if (!patchInitializedRef.current && metaStatus?.latest_patch) {
      setPatch(metaStatus.latest_patch);
      patchInitializedRef.current = true;
    }
  }, [metaStatus?.latest_patch]);

  useEffect(() => {
    let cancelled = false;

    async function loadChampions() {
      try {
        const catalog = await fetchChampionsFromApi();
        if (!cancelled) {
          setChampions(catalog.champions);
          setChampionPositions(catalog.positions);
          setEstimatedChampions(catalog.estimatedChampions);
          setError(null);
        }
      } catch (fetchError) {
        if (!cancelled) {
          setError(
            fetchError instanceof Error
              ? fetchError.message
              : "Erreur lors du chargement des champions",
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingChampions(false);
        }
      }
    }

    async function loadDdragonVersion() {
      try {
        const version = await fetchLatestDdragonVersion();
        if (!cancelled) {
          setDdragonVersion(version);
        }
      } catch {
        // fallback version
      }
    }

    loadChampions();
    loadDdragonVersion();

    return () => {
      cancelled = true;
    };
  }, []);

  function handleReset() {
    botExplanation.skipAll();
    draft.resetDraft();
    postDraft.resetFlow();
  }

  const showDraftNovel = botEnabled && postDraft.phase === "drafting";
  const showExplainNovel = botExplanation.active;
  const showBotNovel = showDraftNovel || showExplainNovel;

  const novelLine = showExplainNovel
    ? (botExplanation.currentStep?.text ?? "")
    : botDialogue.line;
  const novelSide = showExplainNovel ? botExplanation.highlightedSide : botDialogue.botSide;
  const novelVisible = showExplainNovel
    ? Boolean(botExplanation.currentStep?.text)
    : botDialogue.visible;

  const stepLabel =
    showExplainNovel && botExplanation.currentStep
      ? botExplanation.currentStep.champion
        ? `${botExplanation.stepIndex + 1}/${botExplanation.stepCount - 1} — ${botExplanation.currentStep.champion}`
        : "Synthèse d'équipe"
      : null;

  const dataStatusLabel = formatMetaStatusLabel(metaStatus);

  const boardMode =
    postDraft.phase === "confirmRoles"
      ? "confirmRoles"
      : postDraft.phase === "result"
        ? "result"
        : "draft";

  return (
    <div className={`app-shell${showBotNovel ? " app-shell--bot-vn" : ""}`}>
      <div className="mode-toolbar">
        <button type="button" className="worlds-btn worlds-btn--ghost" onClick={onBack}>
          Accueil
        </button>
        <span className="mode-toolbar__label">Draft vs Bot</span>
      </div>
      <main className="app">
        <DraftBoard
          draft={draft}
          ddragonVersion={ddragonVersion}
          patch={patch}
          onPatchChange={setPatch}
          dataStatusLabel={dataStatusLabel}
          predictionMode={predictionMode}
          onPredictionModeChange={setPredictionMode}
          playerSide={playerSide}
          onPlayerSideChange={setPlayerSide}
          botEnabled={botEnabled}
          onBotEnabledChange={setBotEnabled}
          botThinking={botThinking}
          botError={botError}
          mode={boardMode}
          highlightedChampion={
            showExplainNovel ? botExplanation.highlightedChampion : null
          }
          highlightedSide={showExplainNovel ? botExplanation.highlightedSide : null}
          resultBluePicks={
            postDraft.phase === "result" ? postDraft.bluePicks : undefined
          }
          resultRedPicks={
            postDraft.phase === "result" ? postDraft.redPicks : undefined
          }
          onExplainBotChoices={
            botEnabled && postDraft.phase === "result" && !postDraft.isEditing
              ? () => {
                  void botExplanation.start();
                }
              : undefined
          }
          explainLoading={botExplanation.loading}
          explainError={botExplanation.error}
          confirmRoles={
            postDraft.phase === "confirmRoles"
              ? {
                  bluePicks: postDraft.bluePicks,
                  redPicks: postDraft.redPicks,
                  blueConfirmed: postDraft.blueConfirmed,
                  redConfirmed: postDraft.redConfirmed,
                  blueValidation: postDraft.blueValidation,
                  redValidation: postDraft.redValidation,
                  onBluePicksChange: postDraft.updateBluePicks,
                  onRedPicksChange: postDraft.updateRedPicks,
                }
              : undefined
          }
          editComp={
            postDraft.phase === "result" && postDraft.isEditing
              ? {
                  bluePicks: postDraft.bluePicks,
                  redPicks: postDraft.redPicks,
                  onBluePicksChange: postDraft.updateBluePicks,
                  onRedPicksChange: postDraft.updateRedPicks,
                  onSlotEdit: postDraft.selectSlot,
                  selectedSlot: postDraft.selectedSlot,
                }
              : undefined
          }
        >
          {postDraft.phase === "result" ? (
            <>
              {postDraft.isEditing && (
                <EditCompPhase
                  bluePicks={postDraft.bluePicks}
                  redPicks={postDraft.redPicks}
                  blueValidation={postDraft.blueValidation}
                  redValidation={postDraft.redValidation}
                  championPositions={championPositions}
                  champions={champions}
                  bannedChampions={[...draft.blueBans, ...draft.redBans]}
                  ddragonVersion={ddragonVersion}
                  selectedSlot={postDraft.selectedSlot}
                  onReplacePick={postDraft.replaceSelectedPick}
                  onClearSelectedSlot={postDraft.clearSelectedSlot}
                  onDone={postDraft.stopEditing}
                />
              )}
              {!postDraft.selectedSlot && (
                <DraftResult
                  draft={draft}
                  bluePicks={postDraft.bluePicks}
                  redPicks={postDraft.redPicks}
                  patch={patch}
                  predictionMode="pro"
                  ddragonVersion={ddragonVersion}
                  champions={champions}
                  usedChampions={postDraft.usedChampionsForAnalysis}
                  onReset={handleReset}
                  onStartEditing={postDraft.startEditing}
                  isEditing={postDraft.isEditing}
                />
              )}
            </>
          ) : postDraft.phase === "confirmRoles" ? (
            <ConfirmRolesPhase
              bluePicks={postDraft.bluePicks}
              redPicks={postDraft.redPicks}
              blueConfirmed={postDraft.blueConfirmed}
              redConfirmed={postDraft.redConfirmed}
              blueValidation={postDraft.blueValidation}
              redValidation={postDraft.redValidation}
              championPositions={championPositions}
              onConfirmTeam={postDraft.confirmTeam}
            />
          ) : draft.isDraftComplete ? (
            <p className="champion-pool__message">Préparation de l&apos;assignation des rôles…</p>
          ) : (
            <ChampionGrid
              draft={draft}
              champions={champions}
              championPositions={championPositions}
              estimatedChampions={estimatedChampions}
              ddragonVersion={ddragonVersion}
              loading={loadingChampions}
              error={error}
              isPlayerTurn={
                draft.whoseTurn === playerSide && !botThinking
              }
            />
          )}
        </DraftBoard>
        {showBotNovel && (
          <BotVisualNovel
            visible={novelVisible}
            line={novelLine}
            botSide={novelSide}
            explanationMode={showExplainNovel}
            stepLabel={stepLabel}
            isLastStep={showExplainNovel ? botExplanation.isLastStep : false}
            onNext={botExplanation.next}
            onSkipAll={botExplanation.skipAll}
          />
        )}
      </main>
    </div>
  );
}
