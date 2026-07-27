import { useEffect, useMemo, useRef, useState } from "react";
import type { Role } from "../types/draft";
import { simulationPowerBonus, simulationClutchBonus } from "../utils/lecProgression";
import type { MatchSimulationResult, WorldsPhase } from "../types/worlds";
import { buildDraftSequence } from "../draft/sequence";
import { useBotExplanation } from "../hooks/useBotExplanation";
import { useDraftState } from "../hooks/useDraftState";
import { useLecCareer } from "../hooks/useLecCareer";
import { formatMetaStatusLabel, useMetaStatus } from "../hooks/useMetaStatus";
import { usePostDraftFlow } from "../hooks/usePostDraftFlow";
import { useTeamDraftBot } from "../hooks/useTeamDraftBot";
import { useWorldsAmbience, useWorldsDraftSfx } from "../hooks/useWorldsAmbience";
import { useWorldsCoachDialogue } from "../hooks/useWorldsCoachDialogue";
import { fetchChampionsFromApi } from "../services/api";
import { fetchLatestDdragonVersion } from "../utils/ddragon";
import type { PredictResponse as PredictResult } from "../types/predict";
import type { MatchHistorySummary } from "../types/matchHistory";
import { BotVisualNovel } from "./BotVisualNovel";
import { ChampionGrid } from "./ChampionGrid";
import { ConfirmRolesPhase } from "./ConfirmRolesPhase";
import { DraftBoard } from "./DraftBoard";
import { DraftResult } from "./DraftResult";
import { EditCompPhase } from "./EditCompPhase";
import { LecPlayoffsHub } from "./LecPlayoffsHub";
import { LecSeasonEndWithStandings, LecWorldsQualified } from "./LecSeasonEnd";
import { LecSeasonHub } from "./LecSeasonHub";
import { LecSetup } from "./LecSetup";
import { LecStoryScene } from "./LecStoryScene";
import { MatchIntro } from "./MatchIntro";
import { MatchSimulation } from "./MatchSimulation";
import { WorldsCoachPanel } from "./WorldsCoachPanel";
import { WorldsDraftHeader } from "./WorldsDraftHeader";
import { WorldsMatchOutcome } from "./WorldsMatchOutcome";

interface LecCareerAppProps {
  onBack: () => void;
}

export function LecCareerApp({ onBack }: LecCareerAppProps) {
  const lec = useLecCareer();
  const draftSequence = useMemo(
    () => buildDraftSequence(lec.draftPreferences),
    [lec.draftPreferences],
  );
  const draft = useDraftState(draftSequence);
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
  const [lastMatchHistory, setLastMatchHistory] = useState<MatchHistorySummary | null>(null);
  const simulationStartedRef = useRef(false);
  const isPlayoffFlow =
    lec.phase === "playoffIntro" ||
    (lec.phase === "drafting" && Boolean(lec.currentPlayoffMatch)) ||
    (lec.phase === "draftResult" && Boolean(lec.currentPlayoffMatch)) ||
    (lec.phase === "simulating" && Boolean(lec.currentPlayoffMatch));

  const postDraft = usePostDraftFlow(draft, championPositions);
  const playerSide = lec.playerSide;
  const activeOpponent = isPlayoffFlow ? lec.playoffOpponent : lec.currentOpponent;
  const botSide = playerSide === "blue" ? "red" : "blue";
  const botPicks = botSide === "blue" ? postDraft.bluePicks : postDraft.redPicks;
  const opponentPicks = botSide === "blue" ? postDraft.redPicks : postDraft.bluePicks;

  const botExplanation = useBotExplanation({
    botSide,
    botPicks,
    opponentPicks,
    patch,
    mode: "pro",
    enabled: lec.phase === "draftResult" && !postDraft.isEditing,
  });

  const { thinking: botThinking, error: botError, lastMove: botLastMove } = useTeamDraftBot({
    enabled: lec.phase === "drafting" && Boolean(activeOpponent),
    draft,
    playerSide,
    champions,
    patch,
    opponentTeamId: activeOpponent?.id ?? "g2",
    draftSeed: lec.draftSeed,
    opponentRoster: activeOpponent?.roster ?? {
      TOP: "",
      JUNGLE: "",
      MIDDLE: "",
      BOTTOM: "",
      UTILITY: "",
    },
  });

  const ambienceActive = !["setup", "seasonEnd"].includes(lec.phase);
  const ambiencePhase: WorldsPhase =
    lec.phase === "drafting" || lec.phase === "draftResult" ? lec.phase : "bracket";
  const { muted, toggleMute } = useWorldsAmbience(ambienceActive, ambiencePhase);
  useWorldsDraftSfx(lec.phase === "drafting", botLastMove, muted);

  const coachDialogue = useWorldsCoachDialogue({
    enabled: lec.phase === "drafting",
    opponent: activeOpponent,
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
    if (lec.phase !== "drafting" || postDraft.phase !== "result") {
      return;
    }
    lec.showDraftResult();
  }, [lec.phase, postDraft.phase, lec.showDraftResult]);

  function resetMatchState() {
    botExplanation.skipAll();
    draft.resetDraft();
    postDraft.resetFlow();
    setDraftPrediction(null);
    setLastMatchHistory(null);
    simulationStartedRef.current = false;
  }

  function handleReturnToHub() {
    resetMatchState();
    lec.returnToHub();
  }

  function handleMatchOutcomeContinue() {
    resetMatchState();
    if (lec.lastMatchSummary?.context === "playoffs") {
      lec.continueAfterPlayoff();
      return;
    }
    lec.continueAfterMatch();
  }

  function handleBeginDraft() {
    resetMatchState();
    if (isPlayoffFlow) {
      lec.beginPlayoffDraft();
    } else {
      lec.beginDraft();
    }
  }

  function handleLaunchSimulation(prediction?: PredictResult) {
    const activePrediction = prediction ?? draftPrediction;
    if (!lec.playerTeam || !activeOpponent || !activePrediction) {
      return;
    }
    if (simulationStartedRef.current) {
      return;
    }
    simulationStartedRef.current = true;
    if (prediction) {
      setDraftPrediction(prediction);
    }
    lec.beginSimulation();
  }

  function handleSimulationComplete(playerWins: boolean, simulation: MatchSimulationResult) {
    if (lec.playerTeam && activeOpponent) {
      setLastMatchHistory({
        playerTeamName: lec.playerTeam.name,
        opponentTeamName: activeOpponent.name,
        playerSide,
        playerWon: playerWins,
        draftPrediction,
        simulation,
        bluePicks: postDraft.bluePicks,
        redPicks: postDraft.redPicks,
      });
    }
    if (isPlayoffFlow) {
      lec.finishPlayoffMatch(playerWins);
    } else {
      void lec.finishRegularMatch(playerWins);
    }
  }

  const simulationBonuses = useMemo(
    () => ({
      playerRosterPower: Math.min(0.75, 0.5 + simulationPowerBonus(lec.progress)),
      playerClutchBonus: simulationClutchBonus(lec.progress),
    }),
    [lec.progress],
  );

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

  const dataStatusLabel = formatMetaStatusLabel(metaStatus);
  const boardMode =
    postDraft.phase === "confirmRoles"
      ? "confirmRoles"
      : postDraft.phase === "result"
        ? "result"
        : "draft";

  if (lec.phase === "setup") {
    return (
      <LecSetup
        loading={lec.loading}
        error={lec.error}
        onBack={onBack}
        onStart={(teamName, coachName, roster, replaceTeamId) => {
          void lec.startSeason(teamName, coachName, roster, replaceTeamId);
        }}
      />
    );
  }

  if (
    (lec.phase === "storyIntro" || lec.phase === "storyBeat") &&
    lec.pendingStoryChapterId &&
    lec.playerTeam
  ) {
    return (
      <>
        {muteButton}
        <LecStoryScene
          chapterId={lec.pendingStoryChapterId}
          playerTeam={lec.playerTeam}
          onContinue={lec.completeStoryChapter}
        />
      </>
    );
  }

  if (lec.phase === "seasonHub" && lec.season && lec.playerTeam) {
    return (
      <>
        {muteButton}
        <LecSeasonHub
          season={lec.season}
          playerTeam={lec.playerTeam}
          progress={lec.progress}
          onBack={onBack}
          onPlayNext={lec.openNextMatch}
          onUpgrade={lec.purchaseUpgrade}
        />
      </>
    );
  }

  if (lec.phase === "playoffsHub" && lec.season && lec.playerTeam && lec.hydratedPlayoffs.length) {
    return (
      <>
        {muteButton}
        <LecPlayoffsHub
          bracket={lec.hydratedPlayoffs}
          playerTeam={lec.playerTeam}
          onBack={handleReturnToHub}
          onPlayNext={lec.openPlayoffMatch}
        />
      </>
    );
  }

  const introMatch =
    lec.fakeBracketMatch ??
    (lec.currentPlayoffMatch && lec.playerTeam && lec.playoffOpponent
      ? {
          id: lec.currentPlayoffMatch.id,
          round: lec.currentPlayoffMatch.round,
          round_label: lec.currentPlayoffMatch.round_label,
          team_a: { team: lec.playerTeam, source_match_id: null },
          team_b: { team: lec.playoffOpponent, source_match_id: null },
          winner_id: null,
        }
      : null);

  if (
    (lec.phase === "matchIntro" || lec.phase === "playoffIntro") &&
    introMatch &&
    lec.playerTeam &&
    activeOpponent
  ) {
    return (
      <>
        {muteButton}
        <MatchIntro
          match={introMatch}
          playerTeam={lec.playerTeam}
          opponent={activeOpponent}
          draftPreferences={lec.draftPreferences}
          onDraftPreferencesChange={lec.setDraftPreferences}
          onBack={isPlayoffFlow ? () => lec.continueAfterPlayoff() : lec.returnToHub}
          onStartDraft={handleBeginDraft}
        />
      </>
    );
  }

  if (lec.phase === "draftResult" && lec.playerTeam && activeOpponent) {
    return (
      <div className={`app-shell worlds-draft-shell${botExplanation.active ? " app-shell--bot-vn" : ""}`}>
        {muteButton}
        <WorldsDraftHeader
          opponentName={activeOpponent.name}
          phaseLabel="ANALYSE DE LA DRAFT"
          playerSide={playerSide}
          onBack={handleReturnToHub}
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
            highlightedChampion={botExplanation.active ? botExplanation.highlightedChampion : null}
            highlightedSide={botExplanation.active ? botExplanation.highlightedSide : null}
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
            resultPrimaryAction={
              !postDraft.isEditing
                ? {
                    label: draftPrediction ? "Lancer la simulation" : "Calcul de l'analyse…",
                    disabled: !draftPrediction,
                    onClick: () => {
                      if (draftPrediction) {
                        handleLaunchSimulation(draftPrediction);
                      }
                    },
                  }
                : undefined
            }
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
            {postDraft.isEditing ? (
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
            ) : (
              !postDraft.selectedSlot && (
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
                />
              )
            )}
          </DraftBoard>
          {botExplanation.active && (
            <BotVisualNovel
              visible={Boolean(botExplanation.currentStep?.text)}
              line={botExplanation.currentStep?.text ?? ""}
              botSide={botExplanation.highlightedSide}
              explanationMode
              stepLabel={null}
              isLastStep={botExplanation.isLastStep}
              onNext={botExplanation.next}
              onSkipAll={botExplanation.skipAll}
            />
          )}
        </main>
      </div>
    );
  }

  if (lec.phase === "simulating" && lec.playerTeam && activeOpponent && draftPrediction) {
    return (
      <>
        {muteButton}
        <MatchSimulation
          playerTeamName={lec.playerTeam.name}
          opponentTeamName={activeOpponent.name}
          opponentTeamId={activeOpponent.id}
          playerRoster={lec.playerTeam.roster}
          opponentRoster={activeOpponent.roster}
          playerSide={playerSide}
          draftPrediction={draftPrediction}
          playerRosterPower={simulationBonuses.playerRosterPower}
          playerClutchBonus={simulationBonuses.playerClutchBonus}
          onComplete={handleSimulationComplete}
        />
      </>
    );
  }

  if (lec.phase === "matchResult" && lec.lastMatchSummary) {
    return (
      <>
        {muteButton}
        <WorldsMatchOutcome
          playerWon={Boolean(lec.lastPlayerWon)}
          opponentName={lec.lastMatchSummary.opponent_name}
          roundLabel={lec.lastMatchSummary.round_label}
          matchHistory={lastMatchHistory}
          onContinue={handleMatchOutcomeContinue}
        />
      </>
    );
  }

  if (lec.phase === "worldsQualified" && lec.playerTeam) {
    return (
      <>
        {muteButton}
        <LecWorldsQualified
          playerTeamName={lec.playerTeam.name}
          onContinue={() => {
            lec.completeStoryChapter();
            lec.resetCareer();
            onBack();
          }}
        />
      </>
    );
  }

  if (lec.phase === "seasonEnd" && lec.season) {
    const playerRow = lec.season.standings.find((row) => row.is_player_team) ?? null;
    return (
      <>
        {muteButton}
        <LecSeasonEndWithStandings
          playerRow={playerRow}
          worldsQualified={Boolean(playerRow?.worlds_cutoff)}
          standings={lec.season.standings}
          onRestart={lec.resetCareer}
          onBackHome={() => {
            lec.resetCareer();
            onBack();
          }}
        />
      </>
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
        opponentName={activeOpponent?.name ?? "…"}
        phaseLabel={draftPhaseLabel()}
        playerSide={playerSide}
        onBack={handleReturnToHub}
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
        {lec.phase === "drafting" && activeOpponent && (
          <WorldsCoachPanel
            visible={coachDialogue.visible}
            line={coachDialogue.line}
            botSide={coachDialogue.botSide}
            opponent={activeOpponent}
          />
        )}
      </main>
    </div>
  );
}
