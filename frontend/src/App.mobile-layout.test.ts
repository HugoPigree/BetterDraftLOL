import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const cssPath = resolve(dirname(fileURLToPath(import.meta.url)), "./App.css");
const css = readFileSync(cssPath, "utf8");

describe("mobile layout CSS contract", () => {
  it("uses mode-scoped draft layout with a flexible center column", () => {
    expect(css).toMatch(/\.drafter--draft \.drafter__body\s*\{[^}]*minmax\(0,\s*1fr\)/s);
    expect(css).toMatch(/\.drafter--draft \.drafter__center\s*\{[^}]*min-height:\s*180px/s);
  });

  it("keeps champion pool scrollable with a minimum height in draft mode", () => {
    expect(css).toMatch(/\.drafter--draft \.champion-pool__grid\s*\{[^}]*min-height:\s*140px/s);
    expect(css).toMatch(/\.drafter--draft \.champion-pool__grid\s*\{[^}]*overflow:\s*auto/s);
  });

  it("compacts pick strips during draft so the pool can fit on screen", () => {
    expect(css).toMatch(/\.drafter--draft \.splash-slot\s*\{[^}]*max-height:\s*56px/s);
    expect(css).toMatch(/\.drafter--draft \.splash-slot\s*\{[^}]*aspect-ratio:\s*1/s);
  });

  it("shows both teams above confirm/result content", () => {
    expect(css).toMatch(
      /\.drafter__body\s*\{[^}]*grid-template-areas:\s*"blue"\s*"red"\s*"center"/s,
    );
  });

  it("hides the Rival sprite on phone to free vertical space", () => {
    expect(css).toMatch(/@media \(max-width: 860px\)[\s\S]*?\.bot-vn__sprite\s*\{[^}]*display:\s*none/s);
  });

  it("avoids nesting a 5-column grid on sortable pick wrappers", () => {
    expect(css).toMatch(/\.drafter__picks--sortable\s*\{[^}]*display:\s*block/s);
  });
});
