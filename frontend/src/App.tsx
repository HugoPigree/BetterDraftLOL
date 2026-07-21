import { useEffect, useState } from "react";
import type { Role } from "./types/draft";
import "./App.css";
import { ChampionGrid } from "./components/ChampionGrid";
import { DraftBoard } from "./components/DraftBoard";
import { DraftResult } from "./components/DraftResult";
import { useDraftState } from "./hooks/useDraftState";
import { fetchChampionsFromApi } from "./services/api";
import { fetchLatestDdragonVersion } from "./utils/ddragon";

function App() {
  const draft = useDraftState();
  const [champions, setChampions] = useState<string[]>([]);
  const [championPositions, setChampionPositions] = useState<Record<string, Role[]>>({});
  const [ddragonVersion, setDdragonVersion] = useState("14.23.1");
  const [patch, setPatch] = useState("16.13");
  const [loadingChampions, setLoadingChampions] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadChampions() {
      try {
        const catalog = await fetchChampionsFromApi();
        if (!cancelled) {
          setChampions(catalog.champions);
          setChampionPositions(catalog.positions);
          setError(null);
        }
      } catch (fetchError) {
        if (!cancelled) {
          setError(
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
        // fallback version
      }
    }

    loadChampions();
    loadDdragonVersion();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__brand">
          <span className="app-header__logo">DRAFT</span>
          <div>
            <h1>DraftLoL</h1>
          </div>
        </div>
        <label className="patch-select">
          <span>Patch</span>
          <input
            type="text"
            value={patch}
            onChange={(event) => setPatch(event.target.value)}
            disabled={draft.isDraftComplete}
          />
        </label>
      </header>

      <main className="app">
        <DraftBoard draft={draft} ddragonVersion={ddragonVersion}>
          {draft.isDraftComplete ? (
            <DraftResult draft={draft} patch={patch} onReset={draft.resetDraft} />
          ) : (
            <ChampionGrid
              draft={draft}
              champions={champions}
              championPositions={championPositions}
              ddragonVersion={ddragonVersion}
              loading={loadingChampions}
              error={error}
            />
          )}
        </DraftBoard>
      </main>
    </div>
  );
}

export default App;
