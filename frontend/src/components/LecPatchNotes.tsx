import type { LecCareerPatch } from "../types/lec";
import { inVogueChampionsByRole } from "../utils/lecDraftAnalysis";

interface LecPatchNotesProps {
  patch: LecCareerPatch;
  onClose: () => void;
}

export function LecPatchNotes({ patch, onClose }: LecPatchNotesProps) {
  const inVogue = inVogueChampionsByRole(patch, 5);

  return (
    <div className="lec-modal" role="dialog" aria-modal="true" aria-labelledby="lec-patch-notes-title">
      <div className="lec-modal__panel lec-patch-notes">
        <header className="lec-modal__header">
          <div>
            <p className="lec-hub__eyebrow">Meta carrière</p>
            <h2 id="lec-patch-notes-title">{patch.patch_label}</h2>
          </div>
          <button type="button" className="worlds-btn worlds-btn--ghost" onClick={onClose}>
            Fermer
          </button>
        </header>

        <section className="lec-patch-notes__body">
          <p className="lec-patch-notes__intro">
            Champions en vogue ce patch — le style de jeu par équipe se découvre via le scouting.
          </p>

          <h3>En vogue par rôle</h3>
          <div className="lec-patch-notes__roles">
            {Object.entries(inVogue).map(([role, champions]) => (
              <article key={role}>
                <strong>{role}</strong>
                <p>{champions.join(", ")}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
