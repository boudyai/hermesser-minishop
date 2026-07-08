import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(here, "..", "..", "..");
const cardPath = resolve(projectRoot, "src/webapp/components/CornllmTopupCard.svelte");
const screenPath = resolve(projectRoot, "src/webapp/screens/HomeScreen.svelte");

function read(file: string): string {
  return readFileSync(file, "utf8");
}

describe("CornllmTopupCard prop contract", () => {
  it("declares a paymentMethods prop on the card", () => {
    const src = read(cardPath);
    // ponytail: pin the prop name so a future rename shows up here
    // instead of as a silent "no methods available" UI bug.
    expect(src).toMatch(/paymentMethods\s*=\s*\[\]/);
    expect(src).toMatch(/paymentMethods\?:/);
  });

  it("HomeScreen passes paymentMethods to the card (not the bare methods shorthand)", () => {
    const src = read(screenPath);
    // ponytail: the call site must spell paymentMethods= explicitly,
    // because the card declares paymentMethods, not methods. Svelte's
    // {methods} shorthand would set a `methods` prop and the card
    // would silently receive [].
    const callBlock = src.match(/<CornllmTopupCard[\s\S]*?\/>/);
    expect(callBlock, "expected to find <CornllmTopupCard .../> call site").toBeTruthy();
    if (callBlock) {
      const text = callBlock[0];
      expect(text).toMatch(/paymentMethods\s*=\s*\{methods\}/);
      // ponytail: must not use the bare {methods} shorthand at the
      // top of any new line — that's the buggy form (sets prop
      // `methods` instead of `paymentMethods`).
      expect(text).not.toMatch(/^\s*\{methods\}\s*$/m);
    }
  });

  it("submit button is disabled when no payment method selected", () => {
    const src = read(cardPath);
    // ponytail: the disabled condition must include !localMethod.
    // Without it the button looks clickable but submit() returns
    // immediately with an error — same root cause as Bug #4/5: the
    // prop chain drops data, the grid is empty, and the user sees
    // a lit button that does nothing.
    const btnLine = src.match(/disabled=\{.*localMethod.*\}/);
    expect(btnLine, "submit button disabled must include !localMethod").toBeTruthy();
  });
});
