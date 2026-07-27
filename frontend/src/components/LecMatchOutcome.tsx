interface LecMatchOutcomeProps {
  playerWon: boolean;
  opponentName: string;
  roundLabel: string;
  onContinue: () => void;
}

export function LecMatchOutcome({
  playerWon,
  opponentName,
  roundLabel,
  onContinue,
}: LecMatchOutcomeProps) {
  const title = playerWon ? "Victoire" : "Défaite";
  const message = playerWon
    ? `Tu bats ${opponentName}.`
    : `Défaite face à ${opponentName}.`;

  return (
    <div className="worlds-screen worlds-screen--center worlds-outcome">
      <div className="match-outcome">
        <p className="match-outcome__round">{roundLabel}</p>
        <h2>{title}</h2>
        <p>{message}</p>
        <button type="button" className="worlds-btn worlds-btn--primary" onClick={onContinue}>
          Continuer
        </button>
      </div>
    </div>
  );
}
