import type { LecCareerPatch } from "../types/lec";

interface LecPatchNotesProps {
  patch: LecCareerPatch;
  onClose: () => void;
}

export function LecPatchNotes({ patch, onClose }: LecPatchNotesProps) {
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
          <h3>Notes de patch</h3>
          <ul>
            {patch.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>

          <h3>Champions viables (aperçu)</h3>
          <div className="lec-patch-notes__roles">
            {Object.entries(patch.viable_by_role).map(([role, champions]) => (
              <article key={role}>
                <strong>{role}</strong>
                <p>{champions.slice(0, 8).join(", ")}{champions.length > 8 ? "…" : ""}</p>
              </article>
            ))}
          </div>
          <p className="lec-patch-notes__hint">
            Les identités de draft par équipe ne sont pas listées ici — scout tes adversaires avant les matchs.
          </p>
        </section>
      </div>
    </div>
  );
}
