import { useState } from "react";
import { useTypewriter } from "../hooks/useTypewriter";
import type { LecStoryChapter } from "../types/lec";
import type { LecTeam } from "../types/lec";
import { lecCoachPortrait } from "../utils/lecTeamBranding";
import { storyChapterById } from "../utils/lecStory";

interface LecStorySceneProps {
  chapterId: string;
  playerTeam: LecTeam | null;
  onContinue: () => void;
}

export function LecStoryScene({ chapterId, playerTeam, onContinue }: LecStorySceneProps) {
  const chapter = storyChapterById(chapterId);
  const [lineIndex, setLineIndex] = useState(0);
  const line = chapter?.lines[lineIndex];
  const typed = useTypewriter(line?.text ?? "", 18);

  if (!chapter || !line) {
    return null;
  }

  const isLastLine = lineIndex >= chapter.lines.length - 1;

  function handleNext() {
    if (isLastLine) {
      onContinue();
      return;
    }
    setLineIndex((current) => current + 1);
  }

  const portraitTeam =
    line.portraitTeamId && playerTeam
      ? { ...playerTeam, id: line.portraitTeamId }
      : playerTeam;
  const portrait = portraitTeam ? lecCoachPortrait(portraitTeam) : null;

  return (
    <div className="worlds-screen worlds-screen--center lec-story">
      <div className={`lec-story__panel lec-story__panel--${line.mood ?? "neutral"}`}>
        <header className="lec-story__header">
          <span className="lec-story__chapter">{chapter.title}</span>
          <span className="lec-story__progress">
            {lineIndex + 1}/{chapter.lines.length}
          </span>
        </header>

        <div className="lec-story__stage">
          <div className="lec-story__portrait">
            {portrait ? (
              <img src={portrait} alt={line.speaker} />
            ) : (
              <div className="lec-story__portrait-fallback">{line.speaker.slice(0, 1)}</div>
            )}
          </div>
          <div className="lec-story__dialogue">
            <strong className="lec-story__speaker">{line.speaker}</strong>
            <p className="lec-story__text">{typed.displayed}</p>
          </div>
        </div>

        <button
          type="button"
          className="worlds-btn worlds-btn--primary"
          onClick={handleNext}
          disabled={!typed.isComplete}
        >
          {isLastLine ? "Continuer" : "Suite"}
        </button>
      </div>
    </div>
  );
}
