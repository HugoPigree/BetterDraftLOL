import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChampionGrid } from "./components/ChampionGrid";
import type { DraftContext } from "./types/draft";

function mockDraft(overrides: Partial<DraftContext> = {}): DraftContext {
  return {
    state: {
      actionIndex: 0,
      blueBans: [],
      redBans: [],
      bluePicks: [],
      redPicks: [],
      usedChampions: [],
    },
    whoseTurn: "blue",
    currentActionType: "ban",
    currentPhase: "ban1",
    isDraftComplete: false,
    actionIndex: 0,
    totalActions: 20,
    blueBans: [],
    redBans: [],
    bluePicks: [],
    redPicks: [],
    usedChampions: [],
    selectChampion: vi.fn(),
    resetDraft: vi.fn(),
    ...overrides,
  };
}

function poolButton(champion: string): HTMLButtonElement {
  const button = document.querySelector(
    `.champion-pool__grid > button.champion-pool__item[title="${champion}"]`,
  );
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`Champion button missing: ${champion}`);
  }
  return button;
}

describe("ChampionGrid", () => {
  it("renders champions so the pool is visible", () => {
    render(
      <ChampionGrid
        draft={mockDraft()}
        champions={["Ahri", "JarvanIV", "Zed"]}
        championPositions={{
          Ahri: ["MIDDLE"],
          JarvanIV: ["JUNGLE"],
          Zed: ["MIDDLE"],
        }}
        ddragonVersion="14.13.1"
        loading={false}
        error={null}
      />,
    );

    expect(poolButton("Ahri")).toBeInTheDocument();
    expect(poolButton("JarvanIV")).toBeInTheDocument();
    expect(poolButton("Zed")).toBeInTheDocument();
  });

  it("filters by search without emptying the whole pool incorrectly", async () => {
    const user = userEvent.setup();
    render(
      <ChampionGrid
        draft={mockDraft()}
        champions={["Ahri", "JarvanIV", "Zed"]}
        championPositions={{
          Ahri: ["MIDDLE"],
          JarvanIV: ["JUNGLE"],
          Zed: ["MIDDLE"],
        }}
        ddragonVersion="14.13.1"
        loading={false}
        error={null}
      />,
    );

    await user.type(screen.getByPlaceholderText("Chercher…"), "Jarv");

    expect(poolButton("JarvanIV")).toBeInTheDocument();
    expect(document.querySelector('.champion-pool__item[title="Ahri"]')).toBeNull();
  });

  it("picks a champion without assigning a role during draft", async () => {
    const user = userEvent.setup();
    const selectChampion = vi.fn();
    render(
      <ChampionGrid
        draft={mockDraft({
          currentActionType: "pick",
          selectChampion,
        })}
        champions={["Ahri"]}
        championPositions={{ Ahri: ["MIDDLE"] }}
        ddragonVersion="14.13.1"
        loading={false}
        error={null}
      />,
    );

    await user.click(poolButton("Ahri"));
    expect(selectChampion).toHaveBeenCalledWith("Ahri");
  });
});
