import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DraftPick } from "../types/draft";
import type {
  PredictionMode,
  PredictResponse,
  RetrospectiveBanSuggestion,
  RetrospectivePickSuggestion,
} from "../types/predict";
import { askChatbotRules } from "../services/api";
import { EXAMPLE_QUESTIONS } from "../constants/chatbotExamples";
import { getAvailableChampions } from "../utils/draftTeamBuilder";
import { resolveLoserSide } from "../utils/resolveLoserSide";

interface ChatMessage {
  id: string;
  role: "user" | "bot";
  text: string;
  intent?: string;
}

interface DraftChatbotProps {
  result: PredictResponse;
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  patch: string;
  predictionMode: PredictionMode;
  champions: string[];
  usedChampions: string[];
  blueWinProbability: number;
  redWinProbability: number;
  retrospectivePicks: RetrospectivePickSuggestion[];
  retrospectiveBans: RetrospectiveBanSuggestion[];
}

export function DraftChatbot({
  result,
  bluePicks,
  redPicks,
  patch,
  predictionMode,
  champions,
  usedChampions,
  blueWinProbability,
  redWinProbability,
  retrospectivePicks,
  retrospectiveBans,
}: DraftChatbotProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "bot",
      text: "Pose-moi une question sur les scores, les termes du modèle, ou simule un changement de pick.",
    },
  ]);
  const listRef = useRef<HTMLDivElement>(null);

  const loserSide = useMemo(
    () => resolveLoserSide(blueWinProbability, redWinProbability),
    [blueWinProbability, redWinProbability],
  );

  const availableChampions = useMemo(
    () => getAvailableChampions(champions, usedChampions),
    [champions, usedChampions],
  );

  const predictionContext = useMemo(
    () => ({
      mode: predictionMode,
      patch,
      focus_team_side: loserSide,
      blue_team: bluePicks,
      red_team: redPicks,
      prediction: result,
      retrospective_picks: retrospectivePicks.map((item) => ({
        champion: item.champion,
        role: item.role,
        reason: item.reason,
      })),
      retrospective_bans: retrospectiveBans.map((item) => ({
        champion: item.champion,
        role: item.role,
        reason: item.reason,
      })),
    }),
    [
      predictionMode,
      patch,
      loserSide,
      bluePicks,
      redPicks,
      result,
      retrospectivePicks,
      retrospectiveBans,
    ],
  );

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, open]);

  const sendQuestion = useCallback(async () => {
    const question = input.trim();
    if (!question || loading) {
      return;
    }

    setInput("");
    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: "user", text: question },
    ]);
    setLoading(true);

    try {
      const response = await askChatbotRules(question, predictionContext, availableChampions);
      setMessages((prev) => [
        ...prev,
        {
          id: `bot-${Date.now()}`,
          role: "bot",
          text: response.answer,
          intent: response.intent_detected,
        },
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Erreur inconnue";
      setMessages((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, role: "bot", text: message },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, predictionContext, availableChampions]);

  return (
    <section className={`draft-chatbot analysis-section${open ? " draft-chatbot--open" : ""}`}>
      <button
        type="button"
        className="draft-chatbot__toggle analysis-section__title"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        Assistant draft
        <span className="draft-chatbot__chevron">{open ? "▾" : "▸"}</span>
      </button>
      <p className="analysis-section__subtitle draft-chatbot__subtitle">
        Posez une question sur les scores, les termes du modèle, ou simulez un changement de pick.
      </p>

      {open && (
        <div className="draft-chatbot__panel">
          <div className="draft-chatbot__messages" ref={listRef}>
            {messages.map((message) => (
              <div
                key={message.id}
                className={`draft-chatbot__message draft-chatbot__message--${message.role}`}
              >
                <p className="draft-chatbot__message-text">{message.text}</p>
                {message.intent === "unknown" && message.role === "bot" && (
                  <ul className="draft-chatbot__examples">
                    {EXAMPLE_QUESTIONS.map((example) => (
                      <li key={example}>
                        <button
                          type="button"
                          className="draft-chatbot__example-btn"
                          onClick={() => setInput(example)}
                        >
                          {example}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {loading && <p className="draft-chatbot__typing">Réflexion...</p>}
          </div>

          <form
            className="draft-chatbot__form"
            onSubmit={(event) => {
              event.preventDefault();
              void sendQuestion();
            }}
          >
            <input
              type="text"
              className="draft-chatbot__input"
              placeholder="Ex : Pourquoi mon winrate est bas ?"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={loading}
            />
            <button type="submit" className="draft-chatbot__send" disabled={loading || !input.trim()}>
              Envoyer
            </button>
          </form>
        </div>
      )}
    </section>
  );
}
