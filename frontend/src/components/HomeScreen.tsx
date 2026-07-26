import worldsLogo from "../assets/worlds-logo.png";

interface HomeScreenProps {
  onSelectDraft: () => void;
  onSelectWorlds: () => void;
  onSelectLec: () => void;
}

export function HomeScreen({ onSelectDraft, onSelectWorlds, onSelectLec }: HomeScreenProps) {
  return (
    <div className="home-screen">
      <div className="home-screen__backdrop" aria-hidden="true" />
      <div className="home-screen__content">
        <p className="home-screen__eyebrow">League of Legends</p>
        <h1 className="home-screen__title">Better Draft LOL</h1>
        <p className="home-screen__subtitle">
          Entraîne ta draft, mène une carrière LEC ou vise le titre des Worlds.
        </p>

        <div className="home-screen__modes">
          <button type="button" className="home-card" onClick={onSelectDraft}>
            <span className="home-card__label">Mode entraînement</span>
            <strong className="home-card__title">Draft vs Bot</strong>
            <span className="home-card__desc">
              Draft solo contre le bot PRO, analyse ML et suggestions en direct.
            </span>
          </button>

          <button type="button" className="home-card home-card--lec" onClick={onSelectLec}>
            <span className="home-card__label">Mode carrière</span>
            <strong className="home-card__title">LEC Career</strong>
            <span className="home-card__desc">
              Crée ton équipe, joue la saison régulière Bo1, vise les playoffs et la qualification Worlds.
            </span>
          </button>

          <button type="button" className="home-card home-card--worlds" onClick={onSelectWorlds}>
            <img src={worldsLogo} alt="" className="home-card__worlds-logo" aria-hidden="true" />
            <span className="home-card__label">Mode tournoi</span>
            <strong className="home-card__title">Worlds</strong>            <span className="home-card__desc">
              Crée ton équipe, affronte 7 structures pro et remporte le bracket.
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
