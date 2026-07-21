import { useMemo, useState, type KeyboardEvent } from "react";
import { ROLES } from "../hooks/useDraftState";
import type { DraftPick, Role } from "../types/draft";
import { ChampionIcon } from "./ChampionIcon";

interface CompEditorPickerProps {
  slot: { side: "blue" | "red"; slotIndex: number; pick: DraftPick };
  champions: string[];
  championPositions: Record<string, Role[]>;
  bannedChampions: string[];
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  ddragonVersion: string;
  onSelect: (champion: string) => void;
  onCancel: () => void;
}

export function CompEditorPicker({
  slot,
  champions,
  championPositions,
  bannedChampions,
  bluePicks,
  redPicks,
  ddragonVersion,
  onSelect,
  onCancel,
}: CompEditorPickerProps) {
  const [search, setSearch] = useState("");
  const targetRole = ROLES[slot.slotIndex];

  const unavailable = useMemo(() => {
    const used = new Set<string>([...bannedChampions]);
    for (const pick of [...bluePicks, ...redPicks]) {
      if (pick.champion !== slot.pick.champion) {
        used.add(pick.champion);
      }
    }
    return used;
  }, [bannedChampions, bluePicks, redPicks, slot.pick.champion]);

  const options = useMemo(() => {
    const query = search.trim().toLowerCase();
    return champions.filter((name) => {
      if (unavailable.has(name)) {
        return false;
      }
      if (query && !name.toLowerCase().includes(query)) {
        return false;
      }
      return true;
    });
  }, [champions, unavailable, search]);

  const exactMatch = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return null;
    }
    return options.find((name) => name.toLowerCase() === query) ?? null;
  }, [options, search]);

  function handleSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      onCancel();
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const pick = exactMatch ?? options[0];
      if (pick) {
        onSelect(pick);
      }
    }
  }

  return (
    <section className="comp-editor-picker">
      <header className="comp-editor-picker__header">
        <h3>Remplacer {slot.pick.champion}</h3>
        <p>
          Rôle {targetRole} · {slot.side === "blue" ? "Blue" : "Red"} Side — le nouveau champion
          prend ce poste.
        </p>
      </header>

      <input
        type="search"
        className="comp-editor-picker__search"
        placeholder="Tapez un champion (ex. Zac, Yasuo)…"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        onKeyDown={handleSearchKeyDown}
        autoFocus
      />

      {exactMatch && (
        <p className="comp-editor-picker__hint">
          Entrée pour sélectionner <strong>{exactMatch}</strong>
        </p>
      )}

      <ul className="comp-editor-picker__grid">
        {options.slice(0, 24).map((champion) => {
          const roles = championPositions[champion] ?? [];
          const fitsRole = roles.includes(targetRole);
          return (
            <li key={champion}>
              <button
                type="button"
                className={[
                  "comp-editor-picker__option",
                  !fitsRole ? "comp-editor-picker__option--off-role" : "",
                  exactMatch === champion ? "comp-editor-picker__option--match" : "",
                ].join(" ")}
                onClick={() => onSelect(champion)}
              >
                <ChampionIcon championName={champion} version={ddragonVersion} size={40} />
                <span>{champion}</span>
                {!fitsRole && roles.length > 0 && <small>Hors rôle Meraki</small>}
              </button>
            </li>
          );
        })}
      </ul>

      {options.length === 0 && (
        <p className="comp-editor-picker__empty">Aucun champion disponible pour ce slot.</p>
      )}

      {options.length > 24 && (
        <p className="comp-editor-picker__hint">Affinez la recherche pour voir plus de résultats.</p>
      )}

      <button type="button" className="comp-editor-picker__cancel" onClick={onCancel}>
        Annuler (Échap)
      </button>
    </section>
  );
}
