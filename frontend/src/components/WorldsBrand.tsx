interface WorldsBrandProps {
  size?: "sm" | "md" | "lg" | "hero";
  showTitle?: boolean;
  subtitle?: string;
  className?: string;
}

const SIZE_CLASS = {
  sm: "worlds-brand--sm",
  md: "worlds-brand--md",
  lg: "worlds-brand--lg",
  hero: "worlds-brand--hero",
};

export function WorldsBrand({
  size = "md",
  showTitle = true,
  subtitle,
  className = "",
}: WorldsBrandProps) {
  return (
    <div className={["worlds-brand", SIZE_CLASS[size], className].filter(Boolean).join(" ")}>
      <img
        src="/worlds-logo.png"
        alt="Worlds Championship"
        className="worlds-brand__logo"
        draggable={false}
      />
      {showTitle && (
        <div className="worlds-brand__text">
          <span className="worlds-brand__title">Worlds</span>
          {subtitle && <span className="worlds-brand__subtitle">{subtitle}</span>}
        </div>
      )}
    </div>
  );
}
