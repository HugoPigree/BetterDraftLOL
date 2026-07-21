import { useMemo, useState } from "react";
import { ROLES } from "../hooks/useDraftState";
import type { DraftContext, Role } from "../types/draft";
import { ChampionIcon } from "./ChampionIcon";

type RoleFilter = Role | "ALL";

interface ChampionGridProps {
  draft: DraftContext;
  champions: string[];
  championPositions: Record<string, Role[]>;
  ddragonVersion: string;
  loading: boolean;
  error: string | null;
}

const ROLE_LABELS: Record<RoleFilter, string> = {
  ALL: "all",
  TOP: "top",
  JUNGLE: "jungle",
  MIDDLE: "mid",
  BOTTOM: "adc",
  UTILITY: "support",
};

const FILTER_OPTIONS: RoleFilter[] = ["ALL", ...ROLES];

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
}: ChampionGridProps) {
  const [search, setSearch] = useState("");
  const [filterRole, setFilterRole] = useState<RoleFilter>("ALL");
  const [pickRole, setPickRole] = useState<Role>("TOP");

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
  const isDisabled = draft.isDraftComplete || loading || Boolean(error);

  function handleRoleFilter(role: RoleFilter) {
    setFilterRole(role);
    if (role !== "ALL" && isPickTurn) {
      setPickRole(role);
    }
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
              {ROLE_LABELS[role]}
            </button>
          ))}
        </div>

        <input
          type="search"
          className="champion-pool__search"
          placeholder="search by name"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          disabled={isDisabled}
        />
      </header>

      {isPickTurn && filterRole === "ALL" && (
        <p className="champion-pool__hint">
          Pick assigné au rôle <strong>{ROLE_LABELS[pickRole]}</strong> — choisis un filtre de lane pour le changer.
        </p>
      )}

      {loading && <p className="champion-pool__message">Chargement des champions...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && filteredChampions.length === 0 && (
        <p className="champion-pool__message">Aucun champion pour ce filtre.</p>
      )}

      <div className="champion-pool__grid">
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
