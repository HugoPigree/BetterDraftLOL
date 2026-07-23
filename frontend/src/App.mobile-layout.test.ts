import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const cssPath = resolve(dirname(fileURLToPath(import.meta.url)), "./App.css");
const css = readFileSync(cssPath, "utf8");

describe("mobile layout CSS contract", () => {
  it("gives the champion pool the flexible row in draft mode", () => {
    expect(css).toMatch(
      /\.drafter--draft \.drafter__body\s*\{[^}]*minmax\(0,\s*1fr\)\s+auto\s+auto/s,
    );
  });

  it("does not force a min-height that can overflow short phone viewports", () => {
    expect(css).not.toMatch(/\.drafter--draft \.drafter__center\s*\{[^}]*min-height:\s*180px/s);
    expect(css).toMatch(/\.drafter--draft \.drafter__center\s*\{[^}]*min-height:\s*0/s);
  });

  it("keeps the champion pool scrollable in draft mode", () => {
    expect(css).toMatch(/\.drafter--draft \.champion-pool__grid\s*\{[^}]*overflow:\s*auto/s);
  });

  it("compacts pick strips during draft", () => {
    expect(css).toMatch(/\.drafter--draft \.splash-slot\s*\{[^}]*max-height:\s*48px/s);
    expect(css).toMatch(/\.drafter--draft \.splash-slot\s*\{[^}]*aspect-ratio:\s*1/s);
  });

  it("does not inflate the draft footer for the Rival overlay", () => {
    const draftFooterPad = css.match(
      /\.app-shell--bot-vn \.drafter--draft \.drafter__footer\s*\{([^}]*)\}/s,
    );
    expect(draftFooterPad?.[1]).toBeTruthy();
    expect(draftFooterPad?.[1]).not.toMatch(/7\.5rem|6\.5rem|min\(200px/);
  });

  it("shows both teams above confirm/result content", () => {
    expect(css).toMatch(
      /\.drafter--confirmRoles \.drafter__body[\s\S]*?grid-template-areas:\s*"blue"\s*"red"\s*"center"/s,
    );
  });

  it("hides the Rival sprite on phone", () => {
    expect(css).toMatch(/@media \(max-width: 860px\)[\s\S]*?\.bot-vn__sprite\s*\{[^}]*display:\s*none/s);
  });

  it("avoids nesting a 5-column grid on sortable pick wrappers", () => {
    expect(css).toMatch(/\.drafter__picks--sortable\s*\{[^}]*display:\s*block/s);
  });
});
