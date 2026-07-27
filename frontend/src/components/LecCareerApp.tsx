import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Role } from "../types/draft";
import type { LecCareerPatch, LecPlayerProfile, LecTeamIdentity } from "../types/lec";
import type { WorldsPhase } from "../types/worlds";
import { buildDraftSequence } from "../draft/sequence";
import { useCareerDraftBot } from "../hooks/useCareerDraftBot";
import { useDraftState } from "../hooks/useDraftState";
import { useDraftTurnTimer } from "../hooks/useDraftTurnTimer";
import { useLecCareer } from "../hooks/useLecCareer";
import { formatMetaStatusLabel, useMetaStatus } from "../hooks/useMetaStatus";
import { usePostDraftFlow } from "../hooks/usePostDraftFlow";
import { useWorldsAmbience, useWorldsDraftSfx } from "../hooks/useWorldsAmbience";
import { useWorldsCoachDialogue } from "../hooks/useWorldsCoachDialogue";
import { fetchChampionsFromApi } from "../services/api";
import { fetchLatestDdragonVersion } from "../utils/ddragon";
import { analyzeCareerDraft, resolveCareerMatch } from "../utils/lecDraftAnalysis";
import { createScoutDossier } from "../utils/lecScout";
import { opponentForFixture } from "../utils/lecTeamBranding";
import { ChampionGrid } from "./ChampionGrid";
import { ConfirmRolesPhase } from "./ConfirmRolesPhase";
import { DraftBoard } from "./DraftBoard";
import { LecCareerDraftRecap } from "./LecCareerDraftRecap";
import { LecCareerPostDraft } from "./LecCareerPostDraft";
import { LecMatchOutcome } from "./LecMatchOutcome";
import { LecPatchNotes } from "./LecPatchNotes";
import { LecPlayoffsHub } from "./LecPlayoffsHub";
import { LecScoutPanel } from "./LecScoutPanel";
import { LecSeasonEndWithStandings, LecWorldsQualified } from "./LecSeasonEnd";
import { LecSeasonHub } from "./LecSeasonHub";
import { LecSetup } from "./LecSetup";
import { LecStoryScene } from "./LecStoryScene";
import { MatchIntro } from "./MatchIntro";
import { WorldsCoachPanel } from "./WorldsCoachPanel";
import { WorldsDraftHeader } from "./WorldsDraftHeader";

const TURN_TIMER_SECONDS = 12;

const FALLBACK_CAREER_PATCH: LecCareerPatch = {
  patch_id: "LEC-C1",
  patch_label: "LEC Carrière 1.1",
  week: 1,
  tag_shifts: {},
  notes: ["Meta carrière indisponible — relance une nouvelle carrière."],
  viable_by_role: {},
};

const FALLBACK_IDENTITY: LecTeamIdentity = {
  team_id: "unknown",
  label: "Style équilibré",
  tags: ["skirmish"],
  spice_chance: 0.1,
  ban_bias: ["skirmish"],
};

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
  const [showPatchNotes, setShowPatchNotes] = useState(false);
  const [metaLoading, setMetaLoading] = useState(false);
  const isPlayoffFlow =
    lec.phase === "playoffIntro" ||
    (lec.phase === "drafting" && Boolean(lec.currentPlayoffMatch)) ||
    (lec.phase === "draftResult" && Boolean(lec.currentPlayoffMatch));

  const postDraft = usePostDraftFlow(draft, championPositions);
  const playerSide = lec.playerSide;
  const activeOpponent = isPlayoffFlow ? lec.playoffOpponent : lec.currentOpponent;
  const careerPatch = lec.careerPatch ?? FALLBACK_CAREER_PATCH;
  const opponentIdentity =
    (activeOpponent &&
      lec.season?.career_universe?.team_identities[activeOpponent.id]) ||
    FALLBACK_IDENTITY;
  const opponentProfiles: LecPlayerProfile[] =
    (activeOpponent && lec.season?.career_universe?.team_profiles[activeOpponent.id]) || [];
  const careerBotEnabled =
    lec.phase === "drafting" &&
    Boolean(activeOpponent && lec.season?.career_universe && lec.careerPatch);

  const careerDraftAnalysis = useMemo(() => {
    if (lec.phase !== "draftResult") {
      return null;
    }
    return analyzeCareerDraft({
      playerSide,
      bluePicks: postDraft.bluePicks,
      redPicks: postDraft.redPicks,
      patch: careerPatch,
    });
  }, [lec.phase, playerSide, postDraft.bluePicks, postDraft.redPicks, careerPatch]);

  const { thinking: botThinking, error: botError, lastMove: botLastMove } = useCareerDraftBot({
    enabled: careerBotEnabled,
    draft,
    playerSide,
    champions,
    careerPatch,
    teamIdentity: opponentIdentity,
    teamProfiles: opponentProfiles,
    draftSeed: lec.draftSeed,
  });

  const isPlayerDraftTurn =
    lec.phase === "drafting" &&
    draft.whoseTurn === playerSide &&
    !botThinking &&
    !draft.isDraftComplete &&
    Boolean(draft.currentActionType);

  const handleTurnTimerExpire = useCallback(() => {
    if (!isPlayerDraftTurn || draft.isDraftComplete || !draft.currentActionType) {
      return;
    }
    const available = champions.filter((champion) => !draft.usedChampions.includes(champion));
    if (!available.length) {
      return;
    }
    const preferred =
      draft.currentActionType === "pick"
        ? Object.values(careerPatch.viable_by_role)
            .flat()
            .find((champion) => available.includes(champion))
        : undefined;
    draft.selectChampion(preferred ?? available[0]);
  }, [
    careerPatch.viable_by_role,
    champions,
    draft,
    draft.currentActionType,
    draft.isDraftComplete,
    draft.usedChampions,
    isPlayerDraftTurn,
  ]);

  const { remaining: turnTimerRemaining, urgent: turnTimerUrgent } = useDraftTurnTimer({
    enabled: lec.phase === "drafting",
    isPlayerTurn: isPlayerDraftTurn,
    seconds: TURN_TIMER_SECONDS,
    onExpire: handleTurnTimerExpire,
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
    if (lec.phase === "simulating") {
      lec.returnToHub();
    }
  }, [lec.phase, lec.returnToHub]);

  useEffect(() => {
    setMetaLoading(Boolean(lec.season && !lec.season.career_universe && lec.phase !== "setup"));
  }, [lec.season, lec.phase]);

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
    draft.resetDraft();
    postDraft.resetFlow();
  }

  function handleCareerMatchPlay() {
    if (!careerDraftAnalysis) {
      return;
    }
    const playerWon = resolveCareerMatch(careerDraftAnalysis.playerWinProbability);
    if (isPlayoffFlow) {
      lec.finishPlayoffMatch(playerWon);
    } else {
      void lec.finishRegularMatch(playerWon);
    }
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

  const dataStatusLabel = lec.careerPatch
    ? `${lec.careerPatch.patch_label} · Meta carrière`
    : formatMetaStatusLabel(metaStatus);

  const hubNextFixture = useMemo(() => {
    if (!lec.season) {
      return null;
    }
    return (
      lec.season.fixtures.find((fixture) => fixture.is_player_match && !fixture.played) ?? null
    );
  }, [lec.season]);

  const hubNextOpponent = useMemo(() => {
    if (!lec.season || !hubNextFixture) {
      return null;
    }
    return opponentForFixture(lec.season.teams, hubNextFixture);
  }, [lec.season, hubNextFixture]);

  const hubNextOpponentIdentity = useMemo(() => {
    if (!hubNextOpponent || !lec.season?.career_universe) {
      return null;
    }
    return lec.season.career_universe.team_identities[hubNextOpponent.id] ?? null;
  }, [hubNextOpponent, lec.season?.career_universe]);

  const hubNextOpponentDossier = useMemo(() => {
    if (!hubNextOpponent) {
      return null;
    }
    return lec.scoutDossiers[hubNextOpponent.id] ?? createScoutDossier(hubNextOpponent.id);
  }, [hubNextOpponent, lec.scoutDossiers]);
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
        {showPatchNotes && (
          <LecPatchNotes
            patch={lec.careerPatch ?? FALLBACK_CAREER_PATCH}
            onClose={() => setShowPatchNotes(false)}
          />
        )}
        <LecSeasonHub
          season={lec.season}
          playerTeam={lec.playerTeam}
          careerPatch={lec.careerPatch}
          metaLoading={metaLoading}
          nextOpponentIdentity={hubNextOpponentIdentity}
          nextOpponentDossier={hubNextOpponentDossier}
          discussLine={lec.discussLine}
          onDiscuss={lec.discussWithOpponent}
          onBack={onBack}
          onPlayNext={lec.openNextMatch}
          onResetCareer={lec.resetCareer}
          onOpenPatchNotes={() => setShowPatchNotes(true)}
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
          onResetCareer={lec.resetCareer}
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
        <div className="lec-match-intro-wrap">
          <MatchIntro
            match={introMatch}
            playerTeam={lec.playerTeam}
            opponent={activeOpponent}
            draftPreferences={lec.draftPreferences}
            onDraftPreferencesChange={lec.setDraftPreferences}
            onBack={isPlayoffFlow ? () => lec.continueAfterPlayoff() : lec.returnToHub}
            onStartDraft={handleBeginDraft}
          />
          {lec.season?.career_universe && activeOpponent && (
            <LecScoutPanel
              opponentName={activeOpponent.name}
              identity={
                lec.season.career_universe.team_identities[activeOpponent.id] ?? FALLBACK_IDENTITY
              }
              dossier={
                lec.scoutDossiers[activeOpponent.id] ?? createScoutDossier(activeOpponent.id)
              }
              discussLine={lec.discussLine}
              onDiscuss={(action) => lec.discussWithOpponent(activeOpponent.id, action)}
            />
          )}
        </div>
      </>
    );
  }

  if (lec.phase === "draftResult" && lec.playerTeam && activeOpponent && careerDraftAnalysis) {
    return (
      <div className="worlds-screen lec-post-draft-screen">
        {muteButton}
        <header className="lec-post-draft-screen__header">
          <button type="button" className="worlds-btn worlds-btn--ghost" onClick={handleReturnToHub}>
            Retour
          </button>
          <h2>vs {activeOpponent.name}</h2>
        </header>
        <LecCareerPostDraft
          draft={draft}
          ddragonVersion={ddragonVersion}
          bluePicks={postDraft.bluePicks}
          redPicks={postDraft.redPicks}
          playerSide={playerSide}
        >
          <LecCareerDraftRecap
            analysis={careerDraftAnalysis}
            playerTeamName={lec.playerTeam.name}
            opponentTeamName={activeOpponent.name}
            onPlayMatch={handleCareerMatchPlay}
            loading={lec.loading}
          />
        </LecCareerPostDraft>
      </div>
    );
  }

  if (lec.phase === "matchResult" && lec.lastMatchSummary) {
    return (
      <>
        {muteButton}
        <LecMatchOutcome
          playerWon={Boolean(lec.lastPlayerWon)}
          opponentName={lec.lastMatchSummary.opponent_name}
          roundLabel={lec.lastMatchSummary.round_label}
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
      {lec.phase === "drafting" && isPlayerDraftTurn && (
        <div className={`lec-draft-timer${turnTimerUrgent ? " lec-draft-timer--urgent" : ""}`}>
          Temps restant : {turnTimerRemaining}s
        </div>
      )}
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
              isPlayerTurn={isPlayerDraftTurn}
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
