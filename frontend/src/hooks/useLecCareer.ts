import { useCallback, useEffect, useMemo, useState } from "react";
import type { DraftPreferences } from "../types/draft";
import type {
  LecCareerSnapshot,
  LecLastMatchSummary,
  LecPhase,
  LecScoutDossier,
  LecSeasonState,
} from "../types/lec";
import type { WorldsRoster } from "../types/worlds";
import {
  getPlayerPlayoffMatch,
  hydrateLecPlayoffs,
  recordPlayoffWinner,
  resolveNpcPlayoffMatches,
} from "../utils/lecBracket";
import { opponentForFixture } from "../utils/lecTeamBranding";
import { storyChapterForWeek } from "../utils/lecStory";
import type { LecCareerProgress, LecUpgradeKey } from "../types/lec";
import {
  awardProgressAfterMatch,
  createDefaultProgress,
  scoutingDraftSeedSalt,
  spendUpgradePoint,
} from "../utils/lecProgression";
import { createScoutDossier, discussWithStaff } from "../utils/lecScout";
import { recordLecMatchResult, fetchCareerPatch, startLecSeason } from "../services/api";

const STORAGE_KEY = "betterdraft-lec-career-v2";

const DEFAULT_DRAFT_PREFERENCES: DraftPreferences = {
  playerSide: "blue",
  pickOrder: "first",
};

function loadSnapshot(): LecCareerSnapshot | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<LecCareerSnapshot>;
    return {
      ...(parsed as LecCareerSnapshot),
      progress: parsed.progress ?? createDefaultProgress(),
      seasonSeed: parsed.seasonSeed ?? "",
      scoutDossiers: parsed.scoutDossiers ?? {},
    };
  } catch {
    return null;
  }
}

function saveSnapshot(snapshot: LecCareerSnapshot) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
}

export function useLecCareer() {
  const restored = loadSnapshot();
  const [phase, setPhase] = useState<LecPhase>(restored?.phase ?? "setup");
  const [season, setSeason] = useState<LecSeasonState | null>(restored?.season ?? null);
  const [draftPreferences, setDraftPreferences] = useState<DraftPreferences>(
    restored?.draftPreferences ?? DEFAULT_DRAFT_PREFERENCES,
  );
  const [currentFixtureId, setCurrentFixtureId] = useState<string | null>(
    restored?.currentFixtureId ?? null,
  );
  const [currentPlayoffMatchId, setCurrentPlayoffMatchId] = useState<string | null>(
    restored?.currentPlayoffMatchId ?? null,
  );
  const [storyChapterSeen, setStoryChapterSeen] = useState<string[]>(
    restored?.storyChapterSeen ?? [],
  );
  const [pendingStoryChapterId, setPendingStoryChapterId] = useState<string | null>(
    restored?.pendingStoryChapterId ?? null,
  );
  const [afterStoryAction, setAfterStoryAction] = useState<
    "hub" | "match" | "playoffs" | "seasonEnd" | null
  >(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastPlayerWon, setLastPlayerWon] = useState<boolean | null>(null);
  const [lastMatchSummary, setLastMatchSummary] = useState<LecLastMatchSummary | null>(
    restored?.lastMatchSummary ?? null,
  );
  const [progress, setProgress] = useState<LecCareerProgress>(
    restored?.progress ?? createDefaultProgress(),
  );
  const [seasonSeed, setSeasonSeed] = useState(restored?.seasonSeed ?? "");
  const [scoutDossiers, setScoutDossiers] = useState<Record<string, LecScoutDossier>>(
    restored?.scoutDossiers ?? {},
  );
  const [discussLine, setDiscussLine] = useState<string | null>(null);

  useEffect(() => {
    if (phase === "matchResult" && !lastMatchSummary) {
      setPhase("seasonHub");
    }
  }, [phase, lastMatchSummary]);

  const playerTeam = useMemo(
    () => season?.teams.find((team) => team.is_player_team) ?? null,
    [season?.teams],
  );

  const currentFixture = useMemo(() => {
    if (!season || !currentFixtureId) {
      return null;
    }
    return season.fixtures.find((fixture) => fixture.id === currentFixtureId) ?? null;
  }, [season, currentFixtureId]);

  const currentOpponent = useMemo(() => {
    if (!season || !currentFixture) {
      return null;
    }
    return opponentForFixture(season.teams, currentFixture);
  }, [season, currentFixture]);

  const hydratedPlayoffs = useMemo(() => {
    if (!season?.playoffs) {
      return [];
    }
    return hydrateLecPlayoffs(season.playoffs);
  }, [season?.playoffs]);

  const currentPlayoffMatch = useMemo(() => {
    if (!currentPlayoffMatchId || !season?.playoffs) {
      return null;
    }
    return hydratedPlayoffs.find((match) => match.id === currentPlayoffMatchId) ?? null;
  }, [currentPlayoffMatchId, hydratedPlayoffs, season?.playoffs]);

  const playerSide = draftPreferences.playerSide;

  useEffect(() => {
    if (!season) {
      return;
    }
    saveSnapshot({
      phase,
      season,
      draftPreferences,
      currentFixtureId,
      currentPlayoffMatchId,
      storyChapterSeen,
      pendingStoryChapterId,
      lastMatchSummary,
      progress,
      seasonSeed,
      scoutDossiers,
    });
  }, [
    phase,
    season,
    draftPreferences,
    currentFixtureId,
    currentPlayoffMatchId,
    storyChapterSeen,
    pendingStoryChapterId,
    lastMatchSummary,
    progress,
    seasonSeed,
    scoutDossiers,
  ]);

  const queueStoryIfNeeded = useCallback(
    (chapterId: string) => {
      if (storyChapterSeen.includes(chapterId)) {
        return;
      }
      setPendingStoryChapterId(chapterId);
      setPhase("storyBeat");
    },
    [storyChapterSeen],
  );

  const startSeason = useCallback(
    async (
      teamName: string,
      coachName: string,
      roster: WorldsRoster,
      replaceTeamId: string | null,
    ) => {
      setLoading(true);
      setError(null);
      try {
        const response = await startLecSeason(teamName, coachName, roster, replaceTeamId);
        setSeason(response);
        setCurrentFixtureId(null);
        setCurrentPlayoffMatchId(null);
        setStoryChapterSeen([]);
        setPendingStoryChapterId("intro-1");
        setAfterStoryAction("hub");
        setProgress(createDefaultProgress());
        setSeasonSeed(`${teamName}:${Date.now()}`);
        setPhase("storyIntro");
      } catch (startError) {
        setError(
          startError instanceof Error
            ? startError.message
            : "Impossible de lancer la saison LEC",
        );
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  const careerPatch = season?.career_universe?.patch ?? null;

  const syncCareerPatch = useCallback(
    async (week: number) => {
      if (!season?.career_universe) {
        return;
      }
      try {
        const patch = await fetchCareerPatch(season.career_universe.universe_seed, week);
        setSeason({
          ...season,
          career_universe: {
            ...season.career_universe,
            patch,
          },
        });
      } catch {
        // fallback: keep existing patch
      }
    },
    [season],
  );

  const openMatchIntro = useCallback(() => {
    if (!season) {
      return;
    }
    const next = season.fixtures.find(
      (fixture) => fixture.is_player_match && !fixture.played,
    );
    if (!next) {
      return;
    }
    setCurrentFixtureId(next.id);
    setDraftPreferences({
      playerSide: next.week % 2 === 1 ? "blue" : "red",
      pickOrder: next.week % 2 === 1 ? "first" : "last",
    });
    setDiscussLine(null);
    void syncCareerPatch(next.week);
    setPhase("matchIntro");
  }, [season, syncCareerPatch]);

  const completeStoryChapter = useCallback(() => {
    if (!pendingStoryChapterId) {
      setPhase("seasonHub");
      return;
    }
    const chapterId = pendingStoryChapterId;
    setStoryChapterSeen((current) =>
      current.includes(chapterId) ? current : [...current, chapterId],
    );
    setPendingStoryChapterId(null);
    const action = afterStoryAction;
    setAfterStoryAction(null);

    if (action === "match") {
      openMatchIntro();
      return;
    }
    if (action === "playoffs") {
      setPhase("playoffsHub");
      return;
    }
    if (action === "seasonEnd") {
      const playerRow = season?.standings.find((row) => row.is_player_team);
      if (chapterId === "worlds" || playerRow?.worlds_cutoff) {
        setPhase("worldsQualified");
        return;
      }
      setPhase("seasonEnd");
      return;
    }
    setPhase("seasonHub");
  }, [pendingStoryChapterId, afterStoryAction, openMatchIntro, season?.standings]);

  const openNextMatch = useCallback(() => {
    if (!season) {
      return;
    }
    const next = season.fixtures.find(
      (fixture) => fixture.is_player_match && !fixture.played,
    );
    if (!next) {
      if (season.regular_complete) {
        const playerRow = season.standings.find((row) => row.is_player_team);
        if (playerRow?.playoffs_cutoff) {
          setAfterStoryAction("playoffs");
          queueStoryIfNeeded("playoffs");
          if (storyChapterSeen.includes("playoffs")) {
            setPhase("playoffsHub");
          }
        } else {
          setAfterStoryAction("seasonEnd");
          queueStoryIfNeeded("missed-worlds");
        }
      }
      return;
    }

    const weekStory = storyChapterForWeek(next.week);
    if (weekStory && !storyChapterSeen.includes(weekStory.id)) {
      setPendingStoryChapterId(weekStory.id);
      setAfterStoryAction("match");
      setPhase("storyBeat");
      return;
    }

    openMatchIntro();
  }, [season, queueStoryIfNeeded, storyChapterSeen, openMatchIntro]);

  const beginDraft = useCallback(() => {
    setPhase("drafting");
  }, []);

  const showDraftResult = useCallback(() => {
    setPhase("draftResult");
  }, []);

  const beginSimulation = useCallback(() => {
    setPhase("simulating");
  }, []);

  const finishRegularMatch = useCallback(
    async (playerWon: boolean) => {
      if (!season || !currentFixture || !playerTeam) {
        return;
      }
      setLastPlayerWon(playerWon);
      setLoading(true);
      setError(null);
      try {
        const winnerId = playerWon
          ? playerTeam.id
          : currentFixture.team_a_id === playerTeam.id
            ? currentFixture.team_b_id
            : currentFixture.team_a_id;

        const response = await recordLecMatchResult({
          fixture_id: currentFixture.id,
          winner_id: winnerId,
          fixtures: season.fixtures,
          teams: season.teams,
          week: currentFixture.week,
        });

        setSeason({
          ...season,
          fixtures: response.fixtures,
          standings: response.standings,
          regular_complete: response.regular_complete,
          playoffs: response.playoffs,
          current_week: currentFixture.week + 1,
        });
        setLastMatchSummary({
          round_label: currentFixture.round_label,
          opponent_name: currentOpponent?.name ?? "Adversaire",
          context: "regular",
        });
        setCurrentFixtureId(null);
        setProgress((current) => awardProgressAfterMatch(current, playerWon));
        setPhase("matchResult");
      } catch (recordError) {
        setError(
          recordError instanceof Error
            ? recordError.message
            : "Impossible d'enregistrer le résultat",
        );
      } finally {
        setLoading(false);
      }
    },
    [season, currentFixture, playerTeam, currentOpponent],
  );

  const continueAfterMatch = useCallback(() => {
    setLastMatchSummary(null);
    setCurrentFixtureId(null);
    if (!season) {
      return;
    }
    if (season.regular_complete) {
      const playerRow = season.standings.find((row) => row.is_player_team);
      if (playerRow?.playoffs_cutoff) {
        if (!storyChapterSeen.includes("playoffs")) {
          setPendingStoryChapterId("playoffs");
          setAfterStoryAction("playoffs");
          setPhase("storyBeat");
          return;
        }
        setPhase("playoffsHub");
        return;
      }
      if (!storyChapterSeen.includes("missed-worlds")) {
        setPendingStoryChapterId("missed-worlds");
        setAfterStoryAction("seasonEnd");
        setPhase("storyBeat");
        return;
      }
      setPhase("seasonEnd");
      return;
    }
    setPhase("seasonHub");
  }, [season, storyChapterSeen]);

  const openPlayoffMatch = useCallback(() => {
    if (!season?.playoffs) {
      return;
    }
    const prepared = resolveNpcPlayoffMatches(season.playoffs);
    setSeason({ ...season, playoffs: prepared });
    const hydrated = hydrateLecPlayoffs(prepared);
    const next = getPlayerPlayoffMatch(hydrated);
    if (!next) {
      const playerRow = season.standings.find((row) => row.is_player_team);
      if (playerRow && playerRow.rank <= 3) {
        if (!storyChapterSeen.includes("worlds")) {
          setPendingStoryChapterId("worlds");
          setAfterStoryAction("seasonEnd");
          setPhase("storyBeat");
          return;
        }
        setPhase("worldsQualified");
      } else if (playerRow && playerRow.rank <= 6) {
        if (!storyChapterSeen.includes("missed-worlds")) {
          setPendingStoryChapterId("missed-worlds");
          setAfterStoryAction("seasonEnd");
          setPhase("storyBeat");
          return;
        }
        setPhase("seasonEnd");
      } else {
        if (!storyChapterSeen.includes("missed-worlds")) {
          setPendingStoryChapterId("missed-worlds");
          setAfterStoryAction("seasonEnd");
          setPhase("storyBeat");
          return;
        }
        setPhase("seasonEnd");
      }
      return;
    }
    setCurrentPlayoffMatchId(next.id);
    setDraftPreferences({ playerSide: "blue", pickOrder: "first" });
    setPhase("playoffIntro");
  }, [season, storyChapterSeen]);

  const beginPlayoffDraft = useCallback(() => {
    setPhase("drafting");
  }, []);

  const finishPlayoffMatch = useCallback(
    (playerWon: boolean) => {
      if (!season?.playoffs || !currentPlayoffMatch || !playerTeam) {
        return;
      }
      setLastPlayerWon(playerWon);
      const winnerId = playerWon
        ? playerTeam.id
        : currentPlayoffMatch.team_a.team?.id === playerTeam.id
          ? currentPlayoffMatch.team_b.team?.id
          : currentPlayoffMatch.team_a.team?.id;
      if (!winnerId) {
        return;
      }
      let updated = recordPlayoffWinner(season.playoffs, currentPlayoffMatch.id, winnerId);
      updated = resolveNpcPlayoffMatches(updated);
      setSeason({ ...season, playoffs: updated });
      setLastMatchSummary({
        round_label: currentPlayoffMatch.round_label,
        opponent_name:
          (currentPlayoffMatch.team_a.team?.id === playerTeam.id
            ? currentPlayoffMatch.team_b.team?.name
            : currentPlayoffMatch.team_a.team?.name) ?? "Adversaire",
        context: "playoffs",
      });
      setCurrentPlayoffMatchId(null);
      setProgress((current) => awardProgressAfterMatch(current, playerWon));
      setPhase("matchResult");
    },
    [season, currentPlayoffMatch, playerTeam],
  );

  const continueAfterPlayoff = useCallback(() => {
    setLastMatchSummary(null);
    setCurrentPlayoffMatchId(null);
    setPhase("playoffsHub");
  }, []);

  const resetCareer = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setPhase("setup");
    setSeason(null);
    setCurrentFixtureId(null);
    setCurrentPlayoffMatchId(null);
    setStoryChapterSeen([]);
    setPendingStoryChapterId(null);
    setError(null);
    setLastPlayerWon(null);
    setLastMatchSummary(null);
    setProgress(createDefaultProgress());
    setSeasonSeed("");
    setScoutDossiers({});
    setDiscussLine(null);
  }, []);

  const purchaseUpgrade = useCallback((key: LecUpgradeKey) => {
    setProgress((current) => spendUpgradePoint(current, key) ?? current);
  }, []);

  const draftSeed = useMemo(() => {
    const base = currentFixture?.id ?? currentPlayoffMatchId ?? seasonSeed;
    return `${base}${scoutingDraftSeedSalt(progress)}`;
  }, [currentFixture?.id, currentPlayoffMatchId, seasonSeed, progress]);

  const discussWithOpponent = useCallback(
    (opponentTeamId: string, questionIndex: number) => {
      if (!season?.career_universe) {
        return;
      }
      const identity = season.career_universe.team_identities[opponentTeamId];
      if (!identity) {
        return;
      }
      const dossier = scoutDossiers[opponentTeamId] ?? createScoutDossier(opponentTeamId);
      const result = discussWithStaff(dossier, identity, questionIndex);
      setScoutDossiers((current) => ({
        ...current,
        [opponentTeamId]: result.dossier,
      }));
      setDiscussLine(result.line);
    },
    [season?.career_universe, scoutDossiers],
  );

  const returnToHub = useCallback(() => {
    setPhase("seasonHub");
  }, []);

  const fakeBracketMatch = useMemo(() => {
    if (!currentFixture || !playerTeam || !currentOpponent) {
      return null;
    }
    return {
      id: currentFixture.id,
      round: "quarter" as const,
      round_label: currentFixture.round_label,
      team_a: { team: playerTeam, source_match_id: null },
      team_b: { team: currentOpponent, source_match_id: null },
      winner_id: null,
    };
  }, [currentFixture, playerTeam, currentOpponent]);

  const playoffOpponent = useMemo(() => {
    if (!currentPlayoffMatch || !playerTeam) {
      return null;
    }
    const other =
      currentPlayoffMatch.team_a.team?.id === playerTeam.id
        ? currentPlayoffMatch.team_b.team
        : currentPlayoffMatch.team_a.team;
    return other ?? null;
  }, [currentPlayoffMatch, playerTeam]);

  return {
    phase,
    season,
    playerTeam,
    playerSide,
    draftPreferences,
    setDraftPreferences,
    currentFixture,
    currentOpponent,
    currentPlayoffMatch,
    playoffOpponent,
    fakeBracketMatch,
    hydratedPlayoffs,
    loading,
    error,
    lastPlayerWon,
    lastMatchSummary,
    progress,
    draftSeed,
    purchaseUpgrade,
    careerPatch,
    scoutDossiers,
    discussLine,
    discussWithOpponent,
    pendingStoryChapterId,
    startSeason,
    completeStoryChapter,
    openNextMatch,
    beginDraft,
    showDraftResult,
    beginSimulation,
    finishRegularMatch,
    finishPlayoffMatch,
    continueAfterMatch,
    continueAfterPlayoff,
    openPlayoffMatch,
    beginPlayoffDraft,
    resetCareer,
    returnToHub,
  };
}
