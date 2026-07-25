import { useState } from "react";
import type { MatchHistorySummary } from "../types/matchHistory";

interface WorldsMatchOutcomeProps {
  playerWon: boolean;
  opponentName: string;
  roundLabel: string;
  champion?: boolean;
  eliminated?: boolean;
  matchHistory?: MatchHistorySummary | null;
  onContinue: () => void;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function WorldsMatchOutcome({
  playerWon,
  opponentName,
  roundLabel,
  champion,
  eliminated,
  matchHistory,
  onContinue,
}: WorldsMatchOutcomeProps) {
  const [showHistory, setShowHistory] = useState(false);

  let title = playerWon ? "Victoire !" : "Défaite";
  let message = playerWon
    ? `Tu élimines ${opponentName} après la ${roundLabel.toLowerCase()}.`
    : `${opponentName} met fin à ton run Worlds.`;

  if (champion) {
    title = "Champion du Worlds !";
    message = "Tu remportes le tournoi. Draft supérieure, équipe légendaire.";
  } else if (eliminated) {
    title = "Éliminé";
    message = "Ton aventure s'arrête ici. Retente le bracket pour viser le titre.";
  }

  const playerWinPct = matchHistory?.draftPrediction
    ? matchHistory.playerSide === "blue"
      ? matchHistory.draftPrediction.blue_win_probability
      : matchHistory.draftPrediction.red_win_probability
    : null;

  return (
    <div className="worlds-screen worlds-screen--center worlds-outcome">
      <div className="match-outcome">
        <p className="match-outcome__round">{roundLabel}</p>
        <h2>{title}</h2>
        <p>{message}</p>

        {matchHistory && (
          <div className="match-outcome__history">
            <button
              type="button"
              className="worlds-btn worlds-btn--ghost match-outcome__history-toggle"
              onClick={() => setShowHistory((value) => !value)}
            >
              {showHistory ? "Masquer le récap" : "Voir l'historique de la game"}
            </button>

            {showHistory && (
              <div className="match-outcome__history-panel">
                {playerWinPct !== null && (
                  <p className="match-outcome__history-stat">
                    Avantage draft :{" "}
                    <strong>{formatPercent(playerWinPct)}</strong> pour{" "}
                    {matchHistory.playerTeamName}
                  </p>
                )}
                {matchHistory.simulation && (
                  <p className="match-outcome__history-stat">
                    Probabilité pré-match :{" "}
                    <strong>
                      {formatPercent(matchHistory.simulation.player_win_probability)}
                    </strong>
                    {" · "}
                    Durée : {matchHistory.simulation.game_length_minutes} min
                  </p>
                )}

                <div className="match-outcome__comps">
                  <div>
                    <span>Blue</span>
                    <ul>
                      {matchHistory.bluePicks.map((pick) => (
                        <li key={`blue-${pick.champion}`}>{pick.champion}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <span>Red</span>
                    <ul>
                      {matchHistory.redPicks.map((pick) => (
                        <li key={`red-${pick.champion}`}>{pick.champion}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                {matchHistory.simulation?.events && (
                  <ol className="match-outcome__timeline">
                    {matchHistory.simulation.events.map((event, index) => (
                      <li key={`${event.minute}-${index}`}>
                        <span>{event.minute}:00</span>
                        <p>{event.text}</p>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            )}
          </div>
        )}

        <button type="button" className="worlds-btn worlds-btn--primary" onClick={onContinue}>
          {champion || eliminated ? "Retour à l'accueil du mode" : "Retour au bracket"}
        </button>
      </div>
    </div>
  );
}
