interface LecBrandProps {
  size?: "sm" | "md" | "lg";
  subtitle?: string;
}

export function LecBrand({ size = "md", subtitle }: LecBrandProps) {
  return (
    <div className={`lec-brand lec-brand--${size}`}>
      <p className="lec-brand__eyebrow">League of Legends EMEA</p>
      <h1 className="lec-brand__title">LEC Career</h1>
      {subtitle && <p className="lec-brand__subtitle">{subtitle}</p>}
    </div>
  );
}
