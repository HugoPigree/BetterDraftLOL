import { WorldsBrand } from "./WorldsBrand";

interface WorldsDraftHeaderProps {
  opponentName: string;
  phaseLabel: string;
  playerSide: "blue" | "red";
  onBack: () => void;
}

export function WorldsDraftHeader({
  opponentName,
  phaseLabel,
  playerSide,
  onBack,
}: WorldsDraftHeaderProps) {
  return (
    <header className="worlds-cs-header">
      <button type="button" className="worlds-btn worlds-btn--ghost worlds-cs-header__back" onClick={onBack}>
        Bracket
      </button>
      <div className="worlds-cs-header__center">
        <WorldsBrand size="sm" showTitle={false} />
        <p className="worlds-cs-header__phase">{phaseLabel}</p>
        <p className="worlds-cs-header__matchup">
          <span className={`worlds-cs-header__side worlds-cs-header__side--${playerSide}`}>
            Ton équipe
          </span>
          <span className="worlds-cs-header__vs">vs</span>
          <span className="worlds-cs-header__opponent">{opponentName}</span>
        </p>
      </div>
    </header>
  );
}
