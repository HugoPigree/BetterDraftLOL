/**
 * Portraits coach bundlés par Vite — fiables sur Vercel (évite /public servi en SPA fallback).
 */
import bubblingPortrait from "../assets/coaches/bubbling.jpg";
import cvmaxPortrait from "../assets/coaches/cvmax.jpg";
import daenyPortrait from "../assets/coaches/daeny.jpg";
import ggoongPortrait from "../assets/coaches/ggoong.jpg";
import hommePortrait from "../assets/coaches/homme.jpg";
import perkzPortrait from "../assets/coaches/perkz.jpg";
import poppyPortrait from "../assets/coaches/poppy.jpg";
import ryuPortrait from "../assets/coaches/ryu.webp";
import tomPortrait from "../assets/coaches/tom.jpg";
import easyhoonPortrait from "../assets/coaches/easyhoon.jpg";

function coachSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, "");
}

/** Coach name slug → URL résolue au build. */
export const COACH_PORTRAIT_BY_COACH: Record<string, string> = {
  tom: tomPortrait,
  ryu: ryuPortrait,
  daeny: daenyPortrait,
  perkz: perkzPortrait,
  homme: hommePortrait,
  poppy: poppyPortrait,
  cvmax: cvmaxPortrait,
  ggoong: ggoongPortrait,
  bubbling: bubblingPortrait,
  easyhoon: easyhoonPortrait,
};

/** IDs équipes Worlds → URL résolue au build (dist/assets/…). */
export const COACH_PORTRAIT_BY_TEAM_ID: Record<string, string> = {
  t1: tomPortrait,
  geng: ryuPortrait,
  blg: daenyPortrait,
  g2: perkzPortrait,
  hle: hommePortrait,
  tes: poppyPortrait,
  dk: cvmaxPortrait,
  fnatic: ggoongPortrait,
  kc: bubblingPortrait,
  mkoi: easyhoonPortrait,
};

export function bundledCoachPortraitUrl(teamId: string, coachName?: string): string | null {
  if (coachName) {
    const byCoach = COACH_PORTRAIT_BY_COACH[coachSlug(coachName)];
    if (byCoach) {
      return byCoach;
    }
  }

  return COACH_PORTRAIT_BY_TEAM_ID[teamId] ?? null;
}
