import type { ReactNode } from "react";

interface AnalysisSectionProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}

/** Conteneur visuel unifié pour les blocs d'analyse post-draft. */
export function AnalysisSection({
  title,
  subtitle,
  children,
  className = "",
}: AnalysisSectionProps) {
  return (
    <section className={`analysis-section ${className}`.trim()}>
      <header className="analysis-section__header">
        <h3 className="analysis-section__title">{title}</h3>
        {subtitle && <p className="analysis-section__subtitle">{subtitle}</p>}
      </header>
      <div className="analysis-section__body">{children}</div>
    </section>
  );
}
