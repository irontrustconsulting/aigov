/**
 * Snapshot asserting the complete token set defined in primitives.css.
 * Guards against accidental removal or rename of a token that other packages
 * depend on. Values are the V-7-cleared hex values from design doc §2.1/§2.2.
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

const primitivesPath = join(__dirname, "../primitives.css");
const vars = readVars(primitivesPath);

describe("primitives.css — primitive colour ramp", () => {
  const expected: Record<string, string> = {
    "color-paper": "#F4F4F1",
    "color-surface": "#FFFFFF",
    "color-surface-sunken": "#FAFAF8",
    "color-hairline": "#E5E5E0",
    "color-hairline-strong": "#D3D4CE",
    "color-ink-muted": "#696E75",
    "color-ink-secondary": "#4A4F55",
    "color-ink": "#1B1D1E",
    "color-brand": "#1E4651",
    "color-brand-strong": "#123338",
    "color-brand-tint": "#E7F0F0",
  };
  for (const [token, value] of Object.entries(expected)) {
    test(`--${token} = ${value}`, () => {
      expect(vars[token]).toBe(value);
    });
  }
});

describe("primitives.css — provenance channel tokens", () => {
  const expected: Record<string, string> = {
    "prov-ai-suggested": "#6E5A8E",
    "prov-catalogue-curated": "#2E4257",
    "prov-user-confirmed": "#5A6068",
    "prov-user-amended": "#9A5A48",
  };
  for (const [token, value] of Object.entries(expected)) {
    test(`--${token} = ${value}`, () => {
      expect(vars[token]).toBe(value);
    });
  }
  test("exactly 4 provenance tokens (no USER_PROVIDED, V-2)", () => {
    const provTokens = Object.keys(vars).filter((k) => k.startsWith("prov-"));
    expect(provTokens).toHaveLength(4);
    expect(provTokens).not.toContain("prov-user-provided");
  });
});

describe("primitives.css — verdict tone tokens", () => {
  const expected: Record<string, string> = {
    "verdict-neutral": "#696E75",
    "verdict-progress-fill": "#E7F0F0",
    "verdict-progress-text": "#123338",
    "verdict-positive-fill": "#E7F0EC",
    "verdict-positive-text": "#2F5D4A",
    "verdict-attention": "#8A6A2E",
    "verdict-halt-fill": "#872B22",
    "verdict-halt-text": "#FFFFFF",
    "verdict-terminal": "#696E75",
  };
  for (const [token, value] of Object.entries(expected)) {
    test(`--${token} = ${value}`, () => {
      expect(vars[token]).toBe(value);
    });
  }
});

describe("primitives.css — severity channel tokens", () => {
  const exactValues: Record<string, string> = {
    "sev-medium-ink": "#8A6A2E",
    "sev-high-ink": "#A84B36",
    "sev-high-bg": "#F8ECE8",
    "sev-critical-ink": "#FFFFFF",
    "sev-critical-bg": "#872B22",
  };
  for (const [token, value] of Object.entries(exactValues)) {
    test(`--${token} = ${value}`, () => {
      expect(vars[token]).toBe(value);
    });
  }
  test("--sev-low references --color-ink-muted via var()", () => {
    expect(vars["sev-low"]).toContain("var(");
    expect(vars["sev-low"]).toContain("color-ink-muted");
  });
});

describe("primitives.css — motion tokens", () => {
  test("--duration-quick = 120ms", () => expect(vars["duration-quick"]).toBe("120ms"));
  test("--duration-base = 180ms", () => expect(vars["duration-base"]).toBe("180ms"));
  test("--duration-slow = 240ms", () => expect(vars["duration-slow"]).toBe("240ms"));
});

describe("primitives.css — radius tokens", () => {
  test("--radius-sm = 0.25rem (4px)", () => expect(vars["radius-sm"]).toBe("0.25rem"));
  test("--radius-md = 0.375rem (6px)", () => expect(vars["radius-md"]).toBe("0.375rem"));
  test("--radius-lg = 0.5rem (8px)", () => expect(vars["radius-lg"]).toBe("0.5rem"));
});

describe("primitives.css — tier-magnitude channel tokens (FE-16 amended D-48)", () => {
  const expected: Record<string, string> = {
    "tier-prohibited-fill": "#1C2A4F",
    "tier-prohibited-text": "#FFFFFF",
    "tier-high-fill": "#2E4A78",
    "tier-high-text": "#FFFFFF",
    "tier-limited-fill": "#E7ECF5",
    "tier-limited-text": "#36507D",
    "tier-minimal-fill": "#EDEFF4",
    "tier-minimal-text": "#4A5878",
  };
  for (const [token, value] of Object.entries(expected)) {
    test(`--${token} = ${value}`, () => {
      expect(vars[token]).toBe(value);
    });
  }
  test("exactly 4 tier magnitudes (fill+text pairs)", () => {
    const tierFills = Object.keys(vars).filter((k) => k.startsWith("tier-") && k.endsWith("-fill"));
    const tierTexts = Object.keys(vars).filter((k) => k.startsWith("tier-") && k.endsWith("-text"));
    expect(tierFills).toHaveLength(4);
    expect(tierTexts).toHaveLength(4);
  });
});
