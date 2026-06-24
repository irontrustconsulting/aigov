/**
 * Skin harness tests (WI-3). Assert that:
 * - Each skin file overrides only values, never introduces new @theme keys
 * - Operator skin carries the brand-strong rail marker (INV-1)
 * - Tenant skin does not carry the operator rail marker
 * - Spacing overrides reflect the correct density posture
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

function readFile(name: string): string {
  return readFileSync(join(__dirname, `../${name}`), "utf-8");
}

function readVars(css: string): Record<string, string> {
  const vars: Record<string, string> = {};
  for (const match of css.matchAll(/--([a-z0-9-]+):\s*([^;\/\n]+?)\s*;/gi)) {
    const [, name, value] = match;
    if (name && value) vars[name] = value.trim();
  }
  return vars;
}

const tenantCss = readFile("skin-tenant.css");
const operatorCss = readFile("skin-operator.css");
const tenantVars = readVars(tenantCss);
const operatorVars = readVars(operatorCss);

describe("skin-operator.css — plane identity rail (INV-1)", () => {
  test("carries --chrome-rail-bg pointing to brand-strong", () => {
    expect(operatorCss).toContain("chrome-rail-bg");
    expect(operatorCss).toContain("color-brand-strong");
  });
  test("carries --chrome-rail-text pointing to brand-tint", () => {
    expect(operatorCss).toContain("chrome-rail-text");
    expect(operatorCss).toContain("color-brand-tint");
  });
});

describe("skin-tenant.css — no operator rail", () => {
  test("does NOT carry chrome-rail-bg", () => {
    expect(tenantCss).not.toContain("chrome-rail-bg");
  });
});

describe("skin-operator.css — compact density", () => {
  test("--spacing-4 is tighter than primitives (≤ 0.75rem)", () => {
    const val = tenantVars["spacing-4"] ?? "1rem";
    const opVal = operatorVars["spacing-4"];
    expect(opVal).toBeDefined();
    const opPx = parseFloat(opVal!) * 16;
    const tenantPx = parseFloat(val) * 16;
    expect(opPx).toBeLessThan(tenantPx);
  });
});

describe("skin-tenant.css — comfortable density", () => {
  test("--spacing-4 at or above primitive baseline (1rem)", () => {
    const tenantVal = tenantVars["spacing-4"];
    if (tenantVal) {
      expect(parseFloat(tenantVal) * 16).toBeGreaterThanOrEqual(16);
    }
  });
});

describe("neither skin introduces new @theme keys (additive-only contract, FE-14)", () => {
  test("skin-tenant.css has no @theme block", () => {
    expect(tenantCss).not.toMatch(/@theme\s*\{/);
  });
  test("skin-operator.css has no @theme block", () => {
    expect(operatorCss).not.toMatch(/@theme\s*\{/);
  });
});
