/**
 * Portraits coach bundlés par Vite — fiables sur Vercel (évite /public servi en SPA fallback).
 */
import coachFallback from "../assets/coaches/coach-fallback.svg";
import cvmaxPortrait from "../assets/coaches/cvmax.jpg";
import daenyPortrait from "../assets/coaches/daeny.jpg";
import hommePortrait from "../assets/coaches/homme.jpg";
import perkzPortrait from "../assets/coaches/perkz.jpg";
import tomPortrait from "../assets/coaches/tom.jpg";

/** IDs équipes Worlds → URL résolue au build (dist/assets/…). */
export const COACH_PORTRAIT_BY_TEAM_ID: Record<string, string> = {
  t1: tomPortrait,
  geng: coachFallback,
  blg: daenyPortrait,
  g2: perkzPortrait,
  hle: hommePortrait,
  tes: coachFallback,
  dk: cvmaxPortrait,
};

export function bundledCoachPortraitUrl(teamId: string): string | null {
  return COACH_PORTRAIT_BY_TEAM_ID[teamId] ?? null;
}
