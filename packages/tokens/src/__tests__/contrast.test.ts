/**
 * AA contrast check for representative text-on-background token pairs, both
 * skins (FE-3 done-check).
 *
 * Computed directly via the WCAG relative-luminance formula rather than
 * jest-axe's color-contrast rule: that rule depends on real layout
 * (bounding boxes, visibility) that jsdom does not compute, so it reports
 * "incomplete" rather than pass/fail for elements with no real layout — an
 * unreliable signal here. A direct WCAG calculation against the token
 * values themselves is the deterministic check.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

function readVars(path: string): Record<string, string> {
  const css = readFileSync(path, "utf-8");
  const vars: Record<string, string> = {};
  for (const match of css.matchAll(/--([a-z0-9-]+):\s*([^;]+);/gi)) {
    const [, name, value] = match;
    if (name && value) vars[name] = value.trim();
  }
  return vars;
}

function hexToRgb(hex: string): [number, number, number] {
  const m = hex.replace("#", "");
  const full = m.length === 3 ? m.split("").map((c) => c + c).join("") : m;
  const num = parseInt(full, 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function contrastRatio(hexA: string, hexB: string): number {
  const lA = relativeLuminance(hexToRgb(hexA));
  const lB = relativeLuminance(hexToRgb(hexB));
  const [lighter, darker] = lA > lB ? [lA, lB] : [lB, lA];
  return (lighter + 0.05) / (darker + 0.05);
}

const primitives = readVars(join(__dirname, "../primitives.css"));
const tenantSkin = readVars(join(__dirname, "../skin-tenant.css"));
const operatorSkin = readVars(join(__dirname, "../skin-operator.css"));

const AA_NORMAL_TEXT = 4.5;

describe.each([
  ["tenant", tenantSkin],
  ["operator", operatorSkin],
])("%s skin — AA contrast", (_name, skin) => {
  const resolve = (key: string): string => {
    const value = skin[key] ?? primitives[key];
    if (!value) throw new Error(`Token --${key} not found in primitives or skin overrides`);
    return value;
  };

  test("text on bg", () => {
    expect(contrastRatio(resolve("color-text"), resolve("color-bg"))).toBeGreaterThanOrEqual(
      AA_NORMAL_TEXT
    );
  });

  test("text on surface", () => {
    expect(
      contrastRatio(resolve("color-text"), resolve("color-surface"))
    ).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
  });

  test("text-muted on bg", () => {
    expect(
      contrastRatio(resolve("color-text-muted"), resolve("color-bg"))
    ).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
  });
});
