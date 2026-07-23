import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { ROLES } from "../hooks/useDraftState";
import { useMediaQuery } from "../hooks/useMediaQuery";
import type { DraftContext, Role } from "../types/draft";
import { ChampionIcon } from "./ChampionIcon";
import { RoleIcon } from "./RoleIcons";

type RoleFilter = Role | "ALL";
type GridSize = "compact" | "normal" | "large";

interface ChampionGridProps {
  draft: DraftContext;
  champions: string[];
  championPositions: Record<string, Role[]>;
  ddragonVersion: string;
  loading: boolean;
  error: string | null;
  isPlayerTurn?: boolean;
}

const ROLE_LABELS: Record<RoleFilter, string> = {
  ALL: "ALL",
  TOP: "TOP",
  JUNGLE: "JGL",
  MIDDLE: "MID",
  BOTTOM: "ADC",
  UTILITY: "SUP",
};

const FILTER_OPTIONS: RoleFilter[] = ["ALL", ...ROLES];

const DESKTOP_GRID_COLUMNS: Record<GridSize, number> = {
  compact: 6,
  normal: 8,
  large: 10,
};

const MOBILE_GRID_COLUMNS: Record<GridSize, number> = {
  compact: 4,
  normal: 5,
  large: 6,
};

function championMatchesRole(
  champion: string,
  role: Role,
  championPositions: Record<string, Role[]>,
): boolean {
  const positions = championPositions[champion];
  if (!positions?.length) {
    return false;
  }
  return positions.includes(role);
}

export function ChampionGrid({
  draft,
  champions,
  championPositions,
  ddragonVersion,
  loading,
  error,
  isPlayerTurn = true,
}: ChampionGridProps) {
  const isMobile = useMediaQuery("(max-width: 720px)");
  const [search, setSearch] = useState("");
  const [filterRole, setFilterRole] = useState<RoleFilter>("ALL");
  const [pickRole, setPickRole] = useState<Role>("TOP");
  const [gridSize, setGridSize] = useState<GridSize>("normal");

  useEffect(() => {
    if (isMobile) {
      setGridSize("compact");
    }
  }, [isMobile]);

  const bannedChampions = useMemo(
    () => new Set([...draft.blueBans, ...draft.redBans]),
    [draft.blueBans, draft.redBans],
  );

  const pickedChampions = useMemo(
    () =>
      new Set([
        ...draft.bluePicks.map((pick) => pick.champion),
        ...draft.redPicks.map((pick) => pick.champion),
      ]),
    [draft.bluePicks, draft.redPicks],
  );

  const filteredChampions = useMemo(() => {
    const query = search.trim().toLowerCase();

    return champions.filter((name) => {
      if (query && !name.toLowerCase().includes(query)) {
        return false;
      }
      if (filterRole !== "ALL" && !championMatchesRole(name, filterRole, championPositions)) {
        return false;
      }
      return true;
    });
  }, [champions, search, filterRole, championPositions]);

  const isPickTurn = draft.currentActionType === "pick";
  const isDisabled = draft.isDraftComplete || loading || Boolean(error) || !isPlayerTurn;
  const columnMap = isMobile ? MOBILE_GRID_COLUMNS : DESKTOP_GRID_COLUMNS;
  const gridColumns = columnMap[gridSize];

  function handleRoleFilter(role: RoleFilter) {
    setFilterRole(role);
    if (role !== "ALL" && isPickTurn) {
      setPickRole(role);
    }
  }

  function shrinkGrid() {
    setGridSize((current) =>
      current === "large" ? "normal" : current === "normal" ? "compact" : current,
    );
  }

  function growGrid() {
    setGridSize((current) =>
      current === "compact" ? "normal" : current === "normal" ? "large" : current,
    );
  }

  return (
    <div className="champion-pool">
      <header className="champion-pool__toolbar">
        <div className="role-picker">
          {FILTER_OPTIONS.map((role) => (
            <button
              key={role}
              type="button"
              className={`role-picker__btn ${
                role === "ALL" ? "role-picker__btn--all" : `role-picker__btn--${role.toLowerCase()}`
              } ${filterRole === role ? "role-picker__btn--active" : ""}`}
              onClick={() => handleRoleFilter(role)}
              disabled={isDisabled}
              title={role === "ALL" ? "Tous les rôles" : role}
            >
              <RoleIcon role={role} />
              <span className="role-picker__label">{ROLE_LABELS[role]}</span>
            </button>
          ))}
        </div>

        <div className="champion-pool__toolbar-right">
          <div className="grid-size-toggle" aria-label="Taille de la grille">
            <button
              type="button"
              className="grid-size-toggle__btn"
              onClick={shrinkGrid}
              disabled={isDisabled || gridSize === "compact"}
              title="Réduire la grille"
            >
              −
            </button>
            <span className="grid-size-toggle__label">{gridColumns} col.</span>
            <button
              type="button"
              className="grid-size-toggle__btn"
              onClick={growGrid}
              disabled={isDisabled || gridSize === "large"}
              title="Agrandir la grille"
            >
              +
            </button>
          </div>

          <input
            type="search"
            className="champion-pool__search"
            placeholder="Chercher…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            disabled={isDisabled}
          />
        </div>
      </header>

      {isPickTurn && filterRole === "ALL" && (
        <p className="champion-pool__hint">
          Pick assigné au rôle <strong>{ROLE_LABELS[pickRole]}</strong> — filtre un rôle pour le
          changer.
        </p>
      )}

      {loading && <p className="champion-pool__message">Chargement des champions...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && filteredChampions.length === 0 && (
        <p className="champion-pool__message">Aucun champion pour ce filtre.</p>
      )}

      <div
        className="champion-pool__grid"
        style={{ "--grid-cols": gridColumns } as CSSProperties}
      >
        {filteredChampions.map((champion) => {
          const isUsed = draft.usedChampions.includes(champion);
          const isBanned = bannedChampions.has(champion);
          const isPicked = pickedChampions.has(champion);
          const overlay = isBanned ? "ban" : isPicked ? "picked" : "none";

          return (
            <button
              key={champion}
              type="button"
              className={`champion-pool__item ${isUsed ? "champion-pool__item--used" : ""}`}
              disabled={isDisabled || isUsed}
              onClick={() => {
                if (isPickTurn) {
                  draft.selectChampion(champion, pickRole);
                } else {
                  draft.selectChampion(champion);
                }
              }}
              title={champion}
            >
              <ChampionIcon
                championName={champion}
                version={ddragonVersion}
                size={64}
                variant="pool"
                overlay={overlay}
              />
              <span className="champion-pool__name">{champion}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
