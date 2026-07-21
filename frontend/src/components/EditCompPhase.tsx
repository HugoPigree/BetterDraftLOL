import type { DraftPick, Role, Team } from "../types/draft";
import type { RoleValidation } from "../utils/autoAssignRoles";
import { getMerakiMismatchWarnings } from "../utils/autoAssignRoles";
import { CompEditorPicker } from "./CompEditorPicker";

interface EditCompPhaseProps {
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  blueValidation: RoleValidation;
  redValidation: RoleValidation;
  championPositions: Record<string, Role[]>;
  champions: string[];
  bannedChampions: string[];
  ddragonVersion: string;
  selectedSlot: { side: Team; slotIndex: number } | null;
  onReplacePick: (champion: string) => void;
  onClearSelectedSlot: () => void;
  onDone: () => void;
}

export function EditCompPhase({
  bluePicks,
  redPicks,
  blueValidation,
  redValidation,
  championPositions,
  champions,
  bannedChampions,
  ddragonVersion,
  selectedSlot,
  onReplacePick,
  onClearSelectedSlot,
  onDone,
}: EditCompPhaseProps) {
  const selectedPick =
    selectedSlot &&
    (selectedSlot.side === "blue" ? bluePicks : redPicks)[selectedSlot.slotIndex];

  if (selectedSlot && selectedPick) {
    return (
      <CompEditorPicker
        slot={{ ...selectedSlot, pick: selectedPick }}
        champions={champions}
        championPositions={championPositions}
        bannedChampions={bannedChampions}
        bluePicks={bluePicks}
        redPicks={redPicks}
        ddragonVersion={ddragonVersion}
        onSelect={onReplacePick}
        onCancel={onClearSelectedSlot}
      />
    );
  }

  const warnings = [
    ...getMerakiMismatchWarnings(bluePicks, championPositions).map((w) => `Blue : ${w}`),
    ...getMerakiMismatchWarnings(redPicks, championPositions).map((w) => `Red : ${w}`),
  ];

  return (
    <section className="edit-comp">
      <header className="edit-comp__header">
        <h2>Modifier la composition</h2>
        <p>
          Cliquez sur un champion pour le remplacer (tapez son nom au clavier), ou glissez via
          l&apos;icône ⠿ pour changer de rôle. L&apos;analyse se recalcule automatiquement.
        </p>
      </header>

      {(!blueValidation.valid || !redValidation.valid) && (
        <p className="edit-comp__error" role="alert">
          {[blueValidation.message, redValidation.message].filter(Boolean).join(" ")}
        </p>
      )}

      {warnings.length > 0 && (
        <ul className="edit-comp__warnings">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <div className="edit-comp__actions">
        <button type="button" className="edit-comp__done" onClick={onDone}>
          Terminer l&apos;édition
        </button>
      </div>
    </section>
  );
}
