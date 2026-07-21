import { useTypewriter } from "../hooks/useTypewriter";
import type { Team } from "../types/draft";

interface BotVisualNovelProps {
  visible: boolean;
  line: string;
  botSide: Team;
}

const BOT_NAME = "Le Rival";

export function BotVisualNovel({ visible, line, botSide }: BotVisualNovelProps) {
  const { displayed, isComplete, skip } = useTypewriter(line, 24);

  if (!visible || !line) {
    return null;
  }

  return (
    <div
      className={`bot-vn bot-vn--${botSide}`}
      role="region"
      aria-label="Dialogue du bot"
    >
      <div className="bot-vn__stage">
        <img
          className="bot-vn__sprite"
          src="/bot-character.png"
          alt=""
          draggable={false}
        />
        <button
          type="button"
          className="bot-vn__box"
          onClick={skip}
          aria-label={isComplete ? "Dialogue" : "Cliquer pour afficher tout le texte"}
        >
          <span className="bot-vn__name">{BOT_NAME}</span>
          <p className="bot-vn__text">
            {displayed}
            {!isComplete && <span className="bot-vn__cursor" aria-hidden="true" />}
          </p>
          {!isComplete && (
            <span className="bot-vn__hint">Cliquer pour accélérer</span>
          )}
        </button>
      </div>
    </div>
  );
}
