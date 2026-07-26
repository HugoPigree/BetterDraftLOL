import { describe, expect, it } from "vitest";
import {
  buildDraftSequence,
  buildDraftSequenceForFirstPick,
  DRAFT_SEQUENCE,
  firstPickIsBlue,
} from "./sequence";

describe("buildDraftSequence", () => {
  it("keeps standard order when blue side has first pick", () => {
    const sequence = buildDraftSequence({ playerSide: "blue", pickOrder: "first" });
    expect(sequence).toEqual(DRAFT_SEQUENCE);
    expect(sequence.find((step) => step.phase === "pick1")?.team).toBe("blue");
  });

  it("mirrors order when red side has first pick", () => {
    const sequence = buildDraftSequence({ playerSide: "red", pickOrder: "first" });
    expect(sequence.find((step) => step.phase === "pick1")?.team).toBe("red");
  });

  it("mirrors order when blue side has last pick", () => {
    const sequence = buildDraftSequence({ playerSide: "blue", pickOrder: "last" });
    expect(sequence.find((step) => step.phase === "pick1")?.team).toBe("red");
  });

  it("keeps standard order when red side has last pick", () => {
    const sequence = buildDraftSequence({ playerSide: "red", pickOrder: "last" });
    expect(sequence).toEqual(DRAFT_SEQUENCE);
  });

  it("resolves first pick side consistently", () => {
    expect(firstPickIsBlue({ playerSide: "blue", pickOrder: "first" })).toBe(true);
    expect(firstPickIsBlue({ playerSide: "red", pickOrder: "last" })).toBe(true);
    expect(firstPickIsBlue({ playerSide: "red", pickOrder: "first" })).toBe(false);
    expect(firstPickIsBlue({ playerSide: "blue", pickOrder: "last" })).toBe(false);
  });

  it("mirrors every step team when red picks first", () => {
    const mirrored = buildDraftSequenceForFirstPick(false);
    expect(mirrored).toHaveLength(DRAFT_SEQUENCE.length);
    for (let index = 0; index < DRAFT_SEQUENCE.length; index += 1) {
      const original = DRAFT_SEQUENCE[index];
      const flipped = mirrored[index];
      expect(flipped?.phase).toBe(original?.phase);
      expect(flipped?.actionType).toBe(original?.actionType);
      expect(flipped?.team).toBe(original?.team === "blue" ? "red" : "blue");
    }
  });
});
