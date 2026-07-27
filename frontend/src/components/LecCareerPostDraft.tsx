import type { ReactNode } from "react";
import type { DraftContext, DraftPick } from "../types/draft";
import { BanSlot } from "./BanSlot";
import { ChampionSplashSlot } from "./ChampionSplashSlot";

interface LecCareerPostDraftProps {
  draft: DraftContext;
  ddragonVersion: string;
  bluePicks: DraftPick[];
  redPicks: DraftPick[];
  playerSide: "blue" | "red";
  children: ReactNode;
}

export function LecCareerPostDraft({
  draft,
  ddragonVersion,
  bluePicks,
  redPicks,
  playerSide,
  children,
}: LecCareerPostDraftProps) {
  return (
    <div className="lec-post-draft">
      <div className="lec-post-draft__board">
        <aside className="lec-post-draft__side lec-post-draft__side--blue">
          {bluePicks.map((pick, index) => (
            <ChampionSplashSlot
              key={`blue-pick-${index}`}
              pick={pick}
              side="blue"
              index={index}
              highlighted={playerSide === "blue"}
              dimmed={false}
            />
          ))}
        </aside>
        <aside className="lec-post-draft__side lec-post-draft__side--red">
          {redPicks.map((pick, index) => (
            <ChampionSplashSlot
              key={`red-pick-${index}`}
              pick={pick}
              side="red"
              index={index}
              highlighted={playerSide === "red"}
              dimmed={false}
            />
          ))}
        </aside>
      </div>

      <div className="lec-post-draft__bans">
        <div className="lec-post-draft__ban-row">
          {Array.from({ length: 5 }, (_, index) => (
            <BanSlot
              key={`blue-ban-${index}`}
              championName={draft.blueBans[index]}
              version={ddragonVersion}
              side="blue"
              slotIndex={index}
            />
          ))}
        </div>
        <div className="lec-post-draft__ban-row">
          {Array.from({ length: 5 }, (_, index) => (
            <BanSlot
              key={`red-ban-${index}`}
              championName={draft.redBans[index]}
              version={ddragonVersion}
              side="red"
              slotIndex={index}
            />
          ))}
        </div>
      </div>

      {children}
    </div>
  );
}
