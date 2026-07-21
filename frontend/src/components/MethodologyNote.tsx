import type { ReactNode } from "react";

interface MethodologyNoteProps {
  title?: string;
  children: ReactNode;
  disclaimer?: string;
  variant?: "default" | "compact";
}

export function MethodologyNote({
  title,
  children,
  disclaimer,
  variant = "default",
}: MethodologyNoteProps) {
  return (
    <div className={`methodology-note methodology-note--${variant}`}>
      {title && <h4 className="methodology-note__title">{title}</h4>}
      <div className="methodology-note__body">{children}</div>
      {disclaimer && <p className="methodology-note__disclaimer">{disclaimer}</p>}
    </div>
  );
}
