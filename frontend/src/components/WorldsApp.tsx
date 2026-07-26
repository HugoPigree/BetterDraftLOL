import { useEffect, useRef, useState } from "react";
import type { Role } from "../types/draft";
import type { MatchSimulationResult } from "../types/worlds";
import { WorldsCoachPanel } from "./WorldsCoachPanel";
import { WorldsDraftHeader } from "./WorldsDraftHeader";
import { BotVisualNovel } from "./BotVisualNovel";
import { ChampionGrid } from "./ChampionGrid";
import { ConfirmRolesPhase } from "./ConfirmRolesPhase";
import { DraftBoard } from "./DraftBoard";
import { DraftResult } from "./DraftResult";
import { EditCompPhase } from "./EditCompPhase";
import { MatchIntro } from "./MatchIntro";
import { MatchSimulation } from "./MatchSimulation";
import { WorldsBracket } from "./WorldsBracket";
import { WorldsMatchOutcome } from "./WorldsMatchOutcome";
import { WorldsSetup } from "./WorldsSetup";
import { useBotExplanation } from "../hooks/useBotExplanation";
import { useDraftState } from "../hooks/useDraftState";
import { formatMetaStatusLabel, useMetaStatus } from "../hooks/useMetaStatus";
import { usePostDraftFlow } from "../hooks/usePostDraftFlow";
import { useTeamDraftBot } from "../hooks/useTeamDraftBot";
import { useWorldsAmbience, useWorldsDraftSfx } from "../hooks/useWorldsAmbience";
import { useWorldsCoachDialogue } from "../hooks/useWorldsCoachDialogue";
import { useWorldsTournament } from "../hooks/useWorldsTournament";
import { fetchChampionsFromApi, simulateWorldsMatch } from "../services/api";
import { fetchLatestDdragonVersion } from "../utils/ddragon";
import type { PredictResponse as PredictResult } from "../types/predict";
import type { MatchHistorySummary } from "../types/matchHistory";

interface WorldsAppProps {
  onBack: () => void;
}

export function WorldsApp({ onBack }: WorldsAppProps) {
  const worlds = useWorldsTournament();
  const draft = useDraftState();
  const [champions, setChampions] = useState<string[]>([]);
  const [championPositions, setChampionPositions] = useState<Record<string, Role[]>>({});
  const [estimatedChampions, setEstimatedChampions] = useState<string[]>([]);
  const [ddragonVersion, setDdragonVersion] = useState("14.23.1");
  const [patch, setPatch] = useState("16.13");
  const patchInitializedRef = useRef(false);
  const { status: metaStatus } = useMetaStatus();
  const [loadingChampions, setLoadingChampions] = useState(true);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [draftPrediction, setDraftPrediction] = useState<PredictResult | null>(null);
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [simulationResult, setSimulationResult] = useState<MatchSimulationResult | null>(null);
  const [lastPlayerWon, setLastPlayerWon] = useState<boolean | null>(null);
  const [lastMatchHistory, setLastMatchHistory] = useState<MatchHistorySummary | null>(null);
  const simulationStartedRef = useRef(false);
  const prefetchedSimulationRef = useRef<{
    key: string;
    promise: Promise<MatchSimulationResult>;
  } | null>(null);

  const postDraft = usePostDraftFlow(draft, championPositions);
  const playerSide = worlds.playerSide;

  const botSide = playerSide === "blue" ? "red" : "blue";
  const botPicks = botSide === "blue" ? postDraft.bluePicks : postDraft.redPicks;
  const opponentPicks = botSide === "blue" ? postDraft.redPicks : postDraft.bluePicks;

  const botExplanation = useBotExplanation({
    botSide,
    botPicks,
    opponentPicks,
    patch,
    mode: "pro",
    enabled: worlds.phase === "draftResult" && !postDraft.isEditing,
  });

  const { thinking: botThinking, error: botError, lastMove: botLastMove } = useTeamDraftBot({
    enabled: worlds.phase === "drafting" && Boolean(worlds.currentOpponent),
    draft,
    playerSide,
    champions,
    patch,
    opponentTeamId: worlds.currentOpponent?.id ?? "t1",
    opponentRoster: worlds.currentOpponent?.roster ?? {
      TOP: "",
      JUNGLE: "",
      MIDDLE: "",
      BOTTOM: "",
      UTILITY: "",
    },
  });

  const ambienceActive =
    worlds.phase !== "setup" &&
    worlds.phase !== "champion" &&
    worlds.phase !== "eliminated";
  const { muted, toggleMute } = useWorldsAmbience(ambienceActive, worlds.phase);

  useWorldsDraftSfx(worlds.phase === "drafting", botLastMove, muted);

  const coachDialogue = useWorldsCoachDialogue({
    enabled: worlds.phase === "drafting",
    opponent: worlds.currentOpponent,
    draft,
    playerSide,
    botThinking,
    botError,
    lastBotMove: botLastMove,
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
        }
      } catch (fetchError) {
        if (!cancelled) {
          setDraftError(
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
        // fallback
      }
    }

    loadChampions();
    loadDdragonVersion();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (worlds.phase !== "drafting" || postDraft.phase !== "result") {
      return;
    }
    worlds.showDraftResult();
  }, [worlds.phase, postDraft.phase, worlds.showDraftResult]);

  function buildSimulationPrefetchKey(prediction: PredictResult): string | null {
    if (!worlds.currentOpponent) {
      return null;
    }
    return [
      playerSide,
      worlds.currentOpponent.id,
      prediction.blue_win_probability.toFixed(4),
    ].join(":");
  }

  function prefetchSimulation(prediction: PredictResult) {
    if (!worlds.playerTeam || !worlds.currentOpponent) {
      return;
    }
    const key = buildSimulationPrefetchKey(prediction);
    if (!key || prefetchedSimulationRef.current?.key === key) {
      return;
    }
    prefetchedSimulationRef.current = {
      key,
      promise: simulateWorldsMatch(
        playerSide,
        worlds.playerTeam.name,
        worlds.currentOpponent.name,
        prediction.blue_win_probability,
        worlds.currentOpponent.id,
        worlds.playerTeam.roster,
        worlds.currentOpponent.roster,
      ),
    };
  }

  useEffect(() => {
    if (
      worlds.phase !== "draftResult" ||
      !draftPrediction ||
      postDraft.isEditing ||
      simulationStartedRef.current
    ) {
      return;
    }
    prefetchSimulation(draftPrediction);
  }, [
    worlds.phase,
    draftPrediction,
    postDraft.isEditing,
    playerSide,
    worlds.playerTeam,
    worlds.currentOpponent,
  ]);

  async function handleLaunchSimulation(prediction?: PredictResult) {
    const activePrediction = prediction ?? draftPrediction;
    if (!worlds.playerTeam || !worlds.currentOpponent || !activePrediction) {
      return;
    }
    if (simulationStartedRef.current) {
      return;
    }
    simulationStartedRef.current = true;
    if (prediction) {
      setDraftPrediction(prediction);
    }
    setSimulationLoading(true);
    setSimulationError(null);
    setSimulationResult(null);
    worlds.beginSimulation();

    try {
      const prefetchKey = buildSimulationPrefetchKey(activePrediction);
      const prefetched =
        prefetchKey && prefetchedSimulationRef.current?.key === prefetchKey
          ? prefetchedSimulationRef.current.promise
          : simulateWorldsMatch(
              playerSide,
              worlds.playerTeam.name,
              worlds.currentOpponent.name,
              activePrediction.blue_win_probability,
              worlds.currentOpponent.id,
              worlds.playerTeam.roster,
              worlds.currentOpponent.roster,
            );
      const simulation = await prefetched;
      setSimulationResult(simulation);
    } catch (simError) {
      simulationStartedRef.current = false;
      setSimulationError(
        simError instanceof Error ? simError.message : "Simulation impossible",
      );
    } finally {
      setSimulationLoading(false);
    }
  }

  function resetMatchState() {
    botExplanation.skipAll();
    draft.resetDraft();
    postDraft.resetFlow();
    setDraftPrediction(null);
    setSimulationLoading(false);
    setSimulationError(null);
    setSimulationResult(null);
    setLastPlayerWon(null);
    setLastMatchHistory(null);
    prefetchedSimulationRef.current = null;
    simulationStartedRef.current = false;
  }

  function handleBeginDraft() {
    resetMatchState();
    worlds.beginDraft();
  }

  function handleSimulationComplete(playerWins: boolean) {
    if (worlds.playerTeam && worlds.currentOpponent) {
      setLastMatchHistory({
        playerTeamName: worlds.playerTeam.name,
        opponentTeamName: worlds.currentOpponent.name,
        playerSide,
        playerWon: playerWins,
        draftPrediction,
        simulation: simulationResult,
        bluePicks: postDraft.bluePicks,
        redPicks: postDraft.redPicks,
      });
    }
    setLastPlayerWon(playerWins);
    worlds.finishMatch(playerWins);
  }

  function handleOutcomeContinue() {
    resetMatchState();
    worlds.returnToBracket();
  }

  const dataStatusLabel = formatMetaStatusLabel(metaStatus);
  const boardMode =
    postDraft.phase === "confirmRoles"
      ? "confirmRoles"
      : postDraft.phase === "result"
        ? "result"
        : "draft";

  const muteButton = (
    <button
      type="button"
      className="worlds-ambience-toggle"
      onClick={toggleMute}
      aria-label={muted ? "Activer la bande son" : "Couper la bande son"}
    >
      {muted ? "Son off" : "Son on"}
    </button>
  );

  if (worlds.phase === "setup") {
    return (
      <WorldsSetup
        loading={worlds.loading}
        error={worlds.error}
        onBack={onBack}
        onStart={(teamName, coachName, roster) => {
          void worlds.startTournament(teamName, coachName, roster);
        }}
      />
    );
  }

  if (worlds.phase === "bracket" && worlds.playerTeam) {
    return (
      <>
        {muteButton}
        <WorldsBracket
          playerTeam={worlds.playerTeam}
          bracket={worlds.bracket}
          onBack={onBack}
          onPlayNextMatch={worlds.openNextPlayerMatch}
        />
      </>
    );
  }

  if (worlds.phase === "matchIntro" && worlds.currentMatch && worlds.playerTeam && worlds.currentOpponent) {
    return (
      <>
        {muteButton}
        <MatchIntro
          match={worlds.currentMatch}
          playerTeam={worlds.playerTeam}
          opponent={worlds.currentOpponent}
          onBack={worlds.returnToBracket}
          onStartDraft={handleBeginDraft}
        />
      </>
    );
  }

  if (worlds.phase === "draftResult" && worlds.playerTeam && worlds.currentOpponent) {
    const showExplainNovel = botExplanation.active;
    const showBotNovel = showExplainNovel;
    const novelLine = botExplanation.currentStep?.text ?? "";
    const novelSide = botExplanation.highlightedSide;
    const novelVisible = Boolean(botExplanation.currentStep?.text);
    const stepLabel =
      botExplanation.currentStep
        ? botExplanation.currentStep.champion
          ? `${botExplanation.stepIndex + 1}/${botExplanation.stepCount - 1} — ${botExplanation.currentStep.champion}`
          : "Synthèse d'équipe"
        : null;

    return (
      <div className={`app-shell worlds-draft-shell${showBotNovel ? " app-shell--bot-vn" : ""}`}>
        {muteButton}
        <WorldsDraftHeader
          opponentName={worlds.currentOpponent.name}
          phaseLabel="ANALYSE DE LA DRAFT"
          playerSide={playerSide}
          onBack={worlds.returnToBracket}
        />
        <main className="app worlds-cs-main">
          <DraftBoard
            draft={draft}
            ddragonVersion={ddragonVersion}
            patch={patch}
            onPatchChange={setPatch}
            dataStatusLabel={dataStatusLabel}
            predictionMode="pro"
            onPredictionModeChange={() => undefined}
            playerSide={playerSide}
            onPlayerSideChange={() => undefined}
            botEnabled
            onBotEnabledChange={() => undefined}
            botThinking={false}
            botError={null}
            mode="result"
            hideModeControls
            highlightedChampion={showExplainNovel ? botExplanation.highlightedChampion : null}
            highlightedSide={showExplainNovel ? botExplanation.highlightedSide : null}
            resultBluePicks={postDraft.bluePicks}
            resultRedPicks={postDraft.redPicks}
            onExplainBotChoices={
              !postDraft.isEditing
                ? () => {
                    void botExplanation.start();
                  }
                : undefined
            }
            explainLoading={botExplanation.loading}
            explainError={botExplanation.error}
            editComp={
              postDraft.isEditing
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
                onReset={resetMatchState}
                onStartEditing={postDraft.startEditing}
                isEditing={postDraft.isEditing}
                hideReset
                onResultChange={setDraftPrediction}
                primaryAction={{
                  label: "Lancer la simulation",
                  loadingLabel: "Simulation en cours…",
                  loading: simulationLoading,
                  onClick: (result) => {
                    void handleLaunchSimulation(result);
                  },
                }}
              />
            )}
          </DraftBoard>
          {showBotNovel && (
            <BotVisualNovel
              visible={novelVisible}
              line={novelLine}
              botSide={novelSide}
              explanationMode
              stepLabel={stepLabel}
              isLastStep={botExplanation.isLastStep}
              onNext={botExplanation.next}
              onSkipAll={botExplanation.skipAll}
            />
          )}
        </main>
      </div>
    );
  }

  if (worlds.phase === "simulating" && worlds.playerTeam && worlds.currentOpponent) {
    return (
      <>
        {muteButton}
        <MatchSimulation
          loading={simulationLoading}
          error={simulationError}
          result={simulationResult}
          playerTeamName={worlds.playerTeam.name}
          opponentTeamName={worlds.currentOpponent.name}
          playerSide={playerSide}
          draftPrediction={draftPrediction}
          onComplete={handleSimulationComplete}
        />
      </>
    );
  }

  if (worlds.phase === "matchResult" && worlds.currentMatch) {
    return (
      <>
        {muteButton}
        <WorldsMatchOutcome
          playerWon={Boolean(lastPlayerWon)}
          opponentName={worlds.currentOpponent?.name ?? "Adversaire"}
          roundLabel={worlds.currentMatch.round_label}
          matchHistory={lastMatchHistory}
          onContinue={handleOutcomeContinue}
        />
      </>
    );
  }

  if (worlds.phase === "champion" && worlds.playerTeam) {
    return (
      <WorldsMatchOutcome
        playerWon
        opponentName="Worlds"
        roundLabel="Finale"
        champion
        onContinue={() => {
          worlds.resetTournament();
          onBack();
        }}
      />
    );
  }

  if (worlds.phase === "eliminated") {
    return (
      <WorldsMatchOutcome
        playerWon={false}
        opponentName={worlds.currentOpponent?.name ?? "Adversaire"}
        roundLabel={worlds.currentMatch?.round_label ?? "Tournoi"}
        eliminated
        onContinue={() => {
          worlds.resetTournament();
          onBack();
        }}
      />
    );
  }

  function draftPhaseLabel(): string {
    if (postDraft.phase === "confirmRoles") {
      return "CONFIRME TES RÔLES";
    }
    if (draft.isDraftComplete) {
      return "DRAFT TERMINÉE";
    }
    const phase = draft.currentPhase;
    if (phase === "ban1" || phase === "ban2") {
      return "BAN TON CHAMPION";
    }
    return "CHOISIS TON CHAMPION";
  }

  return (
    <div className={`app-shell worlds-draft-shell${coachDialogue.visible ? " app-shell--bot-vn" : ""}`}>
      {muteButton}
      <WorldsDraftHeader
        opponentName={worlds.currentOpponent?.name ?? "…"}
        phaseLabel={draftPhaseLabel()}
        playerSide={playerSide}
        onBack={worlds.returnToBracket}
      />
      <main className="app worlds-cs-main">
        <DraftBoard
          draft={draft}
          ddragonVersion={ddragonVersion}
          patch={patch}
          onPatchChange={setPatch}
          dataStatusLabel={dataStatusLabel}
          predictionMode="pro"
          onPredictionModeChange={() => undefined}
          playerSide={playerSide}
          onPlayerSideChange={() => undefined}
          botEnabled
          onBotEnabledChange={() => undefined}
          botThinking={botThinking}
          botError={botError}
          mode={boardMode}
          hideModeControls
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
        >
          {postDraft.phase === "confirmRoles" ? (
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
              error={draftError}
              isPlayerTurn={draft.whoseTurn === playerSide && !botThinking}
            />
          )}
        </DraftBoard>
        {worlds.phase === "drafting" && worlds.currentOpponent && (
          <WorldsCoachPanel
            visible={coachDialogue.visible}
            line={coachDialogue.line}
            botSide={coachDialogue.botSide}
            opponent={worlds.currentOpponent}
          />
        )}
      </main>
    </div>
  );
}
