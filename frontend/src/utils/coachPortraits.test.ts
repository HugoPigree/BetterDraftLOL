import { describe, expect, it } from "vitest";
import {
  COACH_PORTRAIT_BY_COACH,
  COACH_PORTRAIT_BY_TEAM_ID,
  bundledCoachPortraitUrl,
} from "./coachPortraits";

describe("coach portraits", () => {
  it("maps every Worlds pro team to a bundled photo (not SVG fallback)", () => {
    for (const teamId of ["t1", "geng", "blg", "g2", "hle", "tes", "dk"]) {
      const url = bundledCoachPortraitUrl(teamId);
      expect(url, teamId).toBeTruthy();
      expect(url!, teamId).not.toMatch(/\.svg(\?|$)/);
    }
  });

  it("resolves portraits by coach name slug", () => {
    expect(bundledCoachPortraitUrl("geng", "Ryu")).toBe(COACH_PORTRAIT_BY_COACH.ryu);
    expect(bundledCoachPortraitUrl("tes", "Poppy")).toBe(COACH_PORTRAIT_BY_COACH.poppy);
  });

  it("keeps team id mapping aligned with coach slugs", () => {
    expect(COACH_PORTRAIT_BY_TEAM_ID.geng).toBe(COACH_PORTRAIT_BY_COACH.ryu);
    expect(COACH_PORTRAIT_BY_TEAM_ID.tes).toBe(COACH_PORTRAIT_BY_COACH.poppy);
  });

  it("returns null for unknown custom player teams (letter fallback in UI)", () => {
    expect(bundledCoachPortraitUrl("player", "Mon Coach")).toBeNull();
  });
});
