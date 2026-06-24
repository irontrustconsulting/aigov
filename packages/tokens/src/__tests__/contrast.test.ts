/**
 * WCAG 2.1 contrast gate — design doc §4 / SV-7 / INV-54 §9.
 *
 * Reads token values directly from primitives.css and asserts every intended
 * text pairing clears 4.5:1 (normal) / 3:1 (large) and every
 * meaningful-graphical pairing clears 3:1. Structural separators (hairlines)
 * are exempt as non-1.4.11 UI-component elements (N-4 resolution, §5.9).
 *
 * This test fails the build if a future token edit regresses any pairing.
 * The WCAG formula is computed directly (not via jest-axe / jsdom) because
 * jsdom reports "incomplete" for elements with no real layout, giving an
 * unreliable signal. Direct calculation against token values is deterministic.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

function readVars(path: string): Record<string, string> {
  const css = readFileSync(path, "utf-8");
  const vars: Record<string, string> = {};
  for (const match of css.matchAll(/--([a-z0-9-]+):\s*([^;\/\n]+?)\s*;/gi)) {
    const [, name, value] = match;
    if (name && value) vars[name] = value.trim();
  }
  return vars;
}

const vars = readVars(join(__dirname, "../primitives.css"));

function resolve(token: string): string {
  const raw = vars[token];
  if (!raw) throw new Error(`Token --${token} not found in primitives.css`);
  const varRef = raw.match(/var\(--([a-z0-9-]+)\)/);
  if (varRef?.[1]) {
    const resolved = vars[varRef[1]];
    if (!resolved) throw new Error(`Token --${varRef[1]} (referenced by --${token}) not found`);
    return resolved;
  }
  return raw;
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

function contrastRatio(fgToken: string, bgToken: string): number {
  const lA = relativeLuminance(hexToRgb(resolve(fgToken)));
  const lB = relativeLuminance(hexToRgb(resolve(bgToken)));
  const [lighter, darker] = lA > lB ? [lA, lB] : [lB, lA];
  return (lighter + 0.05) / (darker + 0.05);
}

const AA_TEXT = 4.5;
const AA_LARGE = 3.0;
const AA_GRAPHICAL = 3.0;

describe("Text pairings — must clear 4.5:1 (WCAG AA normal text)", () => {
  const pairs: [string, string][] = [
    ["color-ink", "color-paper"],
    ["color-ink", "color-surface"],
    ["color-ink", "color-surface-sunken"],
    ["color-ink-secondary", "color-paper"],
    ["color-ink-secondary", "color-surface"],
    ["color-ink-muted", "color-paper"],
    ["color-ink-muted", "color-surface"],
    ["color-ink-muted", "color-surface-sunken"],
    ["color-brand", "color-paper"],
    ["color-brand", "color-surface"],
    ["color-brand-strong", "color-brand-tint"],
    ["verdict-progress-text", "verdict-progress-fill"],
    ["verdict-positive-text", "verdict-positive-fill"],
    ["verdict-halt-text", "verdict-halt-fill"],
    ["sev-high-ink", "sev-high-bg"],
    ["sev-critical-ink", "sev-critical-bg"],
  ];
  for (const [fg, bg] of pairs) {
    test(`--${fg} on --${bg} ≥ ${AA_TEXT}:1`, () => {
      expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(AA_TEXT);
    });
  }
});

describe("Meaningful-graphical pairings — must clear 3:1 (WCAG AA 1.4.11)", () => {
  const pairs: [string, string][] = [
    ["verdict-neutral", "color-surface"],
    ["verdict-attention", "color-surface"],
    ["prov-ai-suggested", "color-surface"],
    ["prov-catalogue-curated", "color-surface"],
    ["prov-user-confirmed", "color-surface"],
    ["prov-user-amended", "color-surface"],
    ["sev-low", "color-surface"],
    ["sev-medium-ink", "color-surface"],
  ];
  for (const [fg, bg] of pairs) {
    test(`--${fg} on --${bg} ≥ ${AA_GRAPHICAL}:1`, () => {
      expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(AA_GRAPHICAL);
    });
  }
});

describe("Focus ring visibility — must clear 3:1 against adjacent backgrounds", () => {
  test("--color-brand (focus ring) on --color-paper ≥ 3:1", () => {
    expect(contrastRatio("color-brand", "color-paper")).toBeGreaterThanOrEqual(AA_LARGE);
  });
  test("--color-brand (focus ring) on --color-surface ≥ 3:1", () => {
    expect(contrastRatio("color-brand", "color-surface")).toBeGreaterThanOrEqual(AA_LARGE);
  });
});
