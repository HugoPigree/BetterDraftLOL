import { useEffect, useState } from "react";
import { fetchMetaStatus, type MetaStatusResponse } from "../services/api";

export function useMetaStatus() {
  const [status, setStatus] = useState<MetaStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetchMetaStatus();
        if (!cancelled) {
          setStatus(response);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Statut data indisponible",
          );
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { status, error };
}

export function formatMetaStatusLabel(status: MetaStatusResponse | null): string | null {
  if (!status) {
    return null;
  }
  const updated = status.data_built_at ?? status.oracle_updated_at;
  const dateLabel = updated
    ? new Date(updated).toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
  const games =
    status.oracle_team_games != null
      ? ` · ${status.oracle_team_games.toLocaleString("fr-FR")} games pro`
      : "";
  const estimated =
    status.estimated_champions?.length
      ? ` · ${status.estimated_champions.length} profil(s) estimé(s)`
      : "";
  return `Data pro · patch ${status.latest_patch} · MAJ ${dateLabel}${games}${estimated}`;
}
