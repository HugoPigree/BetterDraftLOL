import { useTypewriter } from "../hooks/useTypewriter";
import type { Team } from "../types/draft";

interface BotVisualNovelProps {
  visible: boolean;
  line: string;
  botSide: Team;
  explanationMode?: boolean;
  stepLabel?: string | null;
  isLastStep?: boolean;
  onNext?: () => void;
  onSkipAll?: () => void;
}

const BOT_NAME = "Le Rival";

export function BotVisualNovel({
  visible,
  line,
  botSide,
  explanationMode = false,
  stepLabel = null,
  isLastStep = false,
  onNext,
  onSkipAll,
}: BotVisualNovelProps) {
  const { displayed, isComplete, skip } = useTypewriter(line, 24);

  if (!visible || !line) {
    return null;
  }

  function handleBoxClick() {
    if (!isComplete) {
      skip();
      return;
    }
    if (explanationMode) {
      onNext?.();
    }
  }

  return (
    <div
      className={`bot-vn bot-vn--${botSide}${explanationMode ? " bot-vn--explain" : ""}`}
      role="region"
      aria-label="Dialogue du bot"
    >
      {explanationMode && (
        <button
          type="button"
          className="bot-vn__backdrop"
          aria-label="Fermer l'explication"
          onClick={onSkipAll}
        />
      )}
      <div className="bot-vn__stage">
        <img
          className="bot-vn__sprite"
          src="/bot-character.png"
          alt=""
          draggable={false}
        />
        <div className="bot-vn__panel">
          <button
            type="button"
            className="bot-vn__box"
            onClick={handleBoxClick}
            aria-label={
              isComplete
                ? explanationMode
                  ? isLastStep
                    ? "Terminer"
                    : "Suivant"
                  : "Dialogue"
                : "Cliquer pour afficher tout le texte"
            }
          >
            <span className="bot-vn__name">{BOT_NAME}</span>
            {stepLabel && <span className="bot-vn__step">{stepLabel}</span>}
            <p className="bot-vn__text">
              {displayed}
              {!isComplete && <span className="bot-vn__cursor" aria-hidden="true" />}
            </p>
            {!isComplete && (
              <span className="bot-vn__hint">Cliquer pour accélérer</span>
            )}
            {isComplete && explanationMode && (
              <span className="bot-vn__hint">
                {isLastStep ? "Cliquer pour terminer" : "Cliquer pour continuer"}
              </span>
            )}
          </button>
          {explanationMode && (
            <div className="bot-vn__actions">
              <button type="button" className="bot-vn__action bot-vn__action--skip" onClick={onSkipAll}>
                Passer
              </button>
              <button
                type="button"
                className="bot-vn__action bot-vn__action--next"
                onClick={() => {
                  if (!isComplete) {
                    skip();
                    return;
                  }
                  onNext?.();
                }}
              >
                {isLastStep ? "Terminer" : "Suivant"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
