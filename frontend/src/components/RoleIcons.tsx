import type { Role } from "../types/draft";

type RoleIconProps = {
  role: Role | "ALL";
  className?: string;
};

export function RoleIcon({ role, className = "" }: RoleIconProps) {
  const cn = `role-icon ${className}`.trim();

  switch (role) {
    case "TOP":
      return (
        <svg className={cn} viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M4 18 12 4l8 14H4zm8-3.5a1.25 1.25 0 1 0 0-2.5 1.25 1.25 0 0 0 0 2.5z"
            fill="currentColor"
          />
        </svg>
      );
    case "JUNGLE":
      return (
        <svg className={cn} viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 3c-1.5 2.2-4 4.2-4 7a4 4 0 0 0 8 0c0-2.8-2.5-4.8-4-7zm-6 9.5C4 14.5 4 18 6.5 20.5 8 21 10 21 12 21s4 0 5.5-.5C20 18 20 14.5 18 12.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      );
    case "MIDDLE":
      return (
        <svg className={cn} viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 2v20M7 7l5-5 5 5M7 17l5 5 5-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "BOTTOM":
      return (
        <svg className={cn} viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M5 19h14l-2-5H7l-2 5zm5-8 2-6 2 6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "UTILITY":
      return (
        <svg className={cn} viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 3 9 9H5l4.5 3.5L7 19l5-3.5L17 19l-2.5-6.5L19 9h-4L12 3z"
            fill="currentColor"
          />
        </svg>
      );
    default:
      return (
        <svg className={cn} viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      );
  }
}
