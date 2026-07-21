import type { CSSProperties } from "react";
import { getChampionIconUrl } from "../utils/ddragon";

interface BanSlotProps {
  championName?: string;
  version: string;
  side: "blue" | "red";
  slotIndex: number;
}

export function BanSlot({ championName, version, side, slotIndex }: BanSlotProps) {
  const isFilled = Boolean(championName);

  return (
    <div
      className={[
        "ban-slot",
        `ban-slot--${side}`,
        isFilled ? "ban-slot--filled" : "ban-slot--empty",
      ].join(" ")}
      style={{ "--ban-index": slotIndex } as CSSProperties}
      title={championName ?? "Ban slot"}
    >
      {isFilled ? (
        <>
          <img
            className="ban-slot__icon"
            src={getChampionIconUrl(championName!, version)}
            alt={championName}
            loading="lazy"
          />
          <div className="ban-slot__dim" aria-hidden="true" />
          <span className="ban-slot__slash" aria-hidden="true" />
          <span className="ban-slot__deny" aria-hidden="true">
            ✕
          </span>
        </>
      ) : (
        <div className="ban-slot__placeholder" aria-hidden="true">
          <svg className="ban-slot__silhouette" viewBox="0 0 32 32">
            <path
              d="M16 4c-5 0-8.5 3.5-9 8v3c0 1 .5 2 1.5 2.5l1 8h13l1-8c1-.5 1.5-1.5 1.5-2.5v-3c-.5-4.5-4-8-9-8z"
              fill="currentColor"
              opacity="0.2"
            />
          </svg>
        </div>
      )}
    </div>
  );
}
