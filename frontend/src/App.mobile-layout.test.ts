import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const cssPath = resolve(dirname(fileURLToPath(import.meta.url)), "./App.css");
const css = readFileSync(cssPath, "utf8");

function media860(): string {
  const start = css.indexOf("@media (max-width: 860px)");
  const end = css.indexOf("@media (max-width: 480px)");
  expect(start).toBeGreaterThanOrEqual(0);
  expect(end).toBeGreaterThan(start);
  return css.slice(start, end);
}

describe("mobile layout CSS contract", () => {
  it("docks Rival in document flow on phone (not fixed overlay)", () => {
    const mobile = media860();
    expect(mobile).toMatch(
      /\.app-shell--bot-vn \.bot-vn\s*\{[^}]*position:\s*relative/s,
    );
    expect(mobile).not.toMatch(/\.app-shell--bot-vn \.bot-vn\s*\{[^}]*position:\s*fixed/s);
  });

  it("hides the Rival sprite on phone", () => {
    expect(media860()).toMatch(/\.bot-vn__sprite\s*\{[^}]*display:\s*none/s);
  });

  it("gives the champion pool the flexible row in draft mode", () => {
    expect(media860()).toMatch(
      /\.drafter--draft \.drafter__body\s*\{[^}]*minmax\(0,\s*1fr\)\s+auto\s+auto/s,
    );
  });

  it("keeps draft pick strips square and full-width", () => {
    const mobile = media860();
    expect(mobile).toMatch(/\.drafter--draft \.splash-slot\s*\{[^}]*aspect-ratio:\s*1\s*\/\s*1/s);
    expect(mobile).toMatch(/\.drafter__picks\s*\{[^}]*grid-template-columns:\s*repeat\(5/s);
  });

  it("stacks the mobile footer so the action never crushes ban slots", () => {
    const mobile = media860();
    expect(mobile).toMatch(
      /\.drafter__footer\s*\{[^}]*grid-template-areas:\s*"action action"\s*"bluebans redbans"/s,
    );
    expect(mobile).toMatch(/\.drafter__bans--blue\s*\{[^}]*grid-area:\s*bluebans/s);
    expect(mobile).toMatch(/\.drafter__action\s*\{[^}]*grid-area:\s*action/s);
  });

  it("does not inflate the draft footer for the Rival overlay", () => {
    const mobile = media860();
    expect(mobile).not.toMatch(/7\.5rem|min\(200px/);
    expect(mobile).toMatch(/\.app-shell--bot-vn \.drafter__footer\s*\{[^}]*padding-bottom:\s*0\.25rem/s);
  });

  it("shows both teams above confirm/result content", () => {
    expect(media860()).toMatch(
      /\.drafter--confirmRoles \.drafter__body[\s\S]*?grid-template-areas:\s*"blue"\s*"red"\s*"center"/s,
    );
  });

  it("avoids nesting a 5-column grid on sortable pick wrappers", () => {
    expect(media860()).toMatch(/\.drafter__picks--sortable\s*\{[^}]*display:\s*block/s);
  });
});
