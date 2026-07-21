import { useEffect, useState } from "react";
import type { Role, Team } from "./types/draft";
import type { PredictionMode } from "./types/predict";
import "./App.css";
import { BotVisualNovel } from "./components/BotVisualNovel";
import { ChampionGrid } from "./components/ChampionGrid";
import { ConfirmRolesPhase } from "./components/ConfirmRolesPhase";
import { DraftBoard } from "./components/DraftBoard";
import { DraftResult } from "./components/DraftResult";
import { EditCompPhase } from "./components/EditCompPhase";
import { useBotDialogue } from "./hooks/useBotDialogue";
import { useDraftBot } from "./hooks/useDraftBot";
import { useDraftState } from "./hooks/useDraftState";
import { usePostDraftFlow } from "./hooks/usePostDraftFlow";
import { fetchChampionsFromApi } from "./services/api";
import { fetchLatestDdragonVersion } from "./utils/ddragon";

function App() {
  const draft = useDraftState();
  const [champions, setChampions] = useState<string[]>([]);
  const [championPositions, setChampionPositions] = useState<Record<string, Role[]>>({});
  const [ddragonVersion, setDdragonVersion] = useState("14.23.1");
  const [patch, setPatch] = useState("16.13");
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

  useEffect(() => {
    let cancelled = false;

    async function loadChampions() {
      try {
        const catalog = await fetchChampionsFromApi();
        if (!cancelled) {
          setChampions(catalog.champions);
          setChampionPositions(catalog.positions);
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
    draft.resetDraft();
    postDraft.resetFlow();
  }

  const showBotNovel = botEnabled && postDraft.phase === "drafting";

  const boardMode =
    postDraft.phase === "confirmRoles"
      ? "confirmRoles"
      : postDraft.phase === "result"
        ? "result"
        : "draft";

  return (
    <div className={`app-shell${showBotNovel ? " app-shell--bot-vn" : ""}`}>
      <main className="app">
        <DraftBoard
          draft={draft}
          ddragonVersion={ddragonVersion}
          patch={patch}
          onPatchChange={setPatch}
          predictionMode={predictionMode}
          onPredictionModeChange={setPredictionMode}
          playerSide={playerSide}
          onPlayerSideChange={setPlayerSide}
          botEnabled={botEnabled}
          onBotEnabledChange={setBotEnabled}
          botThinking={botThinking}
          botError={botError}
          mode={boardMode}
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
                  predictionMode={predictionMode}
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
            visible={botDialogue.visible}
            line={botDialogue.line}
            botSide={botDialogue.botSide}
          />
        )}
      </main>
    </div>
  );
}

export default App;
