import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useDraftState } from "./hooks/useDraftState";

describe("useDraftState", () => {
  it("stores picks without locking a role", () => {
    const { result } = renderHook(() => useDraftState());

    const champions = [
      "Aatrox",
      "Ahri",
      "Akali",
      "Alistar",
      "Amumu",
      "Anivia",
      "Annie",
    ];

    act(() => {
      for (const champion of champions) {
        result.current.selectChampion(champion);
      }
    });

    // 6 bans then first blue pick (Annie)
    expect(result.current.bluePicks).toEqual([{ champion: "Annie" }]);
    expect(result.current.bluePicks[0]?.role).toBeUndefined();
  });
});
