import { render } from "@testing-library/react";
import { VerdictChip, TONE_MAP, LABEL_MAP } from "../verdict-chip";
import { expectNoAxeViolations } from "../../../test-utils/axe";

/**
 * Live members per V-5 / P-6 pg_enum dump (5 enums — eu_ai_act_tier removed at
 * V1, migrated to TierBadge per D-48/INV-64). 28 enum members across 5 enums.
 * Keys are uppercase as stored in pg_enum; wire values are lowercase snake_case.
 */
const LIVE_MEMBERS: Record<string, string[]> = {
  assessment_status: ["APPROVED", "DRAFT", "IN_REVIEW", "NEEDS_REFRESH"],
  lifecycle_state: [
    "AUTHORISED", "DEPLOYED", "HALTED_PROHIBITED", "HELD", "INTAKE",
    "PENDING_AUTHORISATION", "PRODUCT_CHECK", "REQUESTED", "RETIRED",
    "TREATMENT_PENDING", "UNDER_ASSESSMENT", "VENDOR_CHECK",
  ],
  approval_status: ["APPROVED", "EXPIRED", "NOT_STARTED", "REJECTED", "UNDER_REVIEW"],
  coverage_status: ["OPEN", "PARTIAL", "SATISFIED"],
  classification_status: ["APPROVED", "CHANGES_REQUESTED", "NEEDS_REFRESH", "PENDING_REVIEW"],
};

describe("VerdictChip — every live member resolves to a tone (no fallthrough)", () => {
  for (const [enumName, members] of Object.entries(LIVE_MEMBERS)) {
    describe(enumName, () => {
      for (const member of members) {
        test(`${member} has a tone in TONE_MAP`, () => {
          expect(TONE_MAP[member]).toBeDefined();
          expect(["neutral", "progress", "positive", "attention", "halt", "terminal"]).toContain(
            TONE_MAP[member]
          );
        });
      }
    });
  }
});

describe("VerdictChip — no invented member in TONE_MAP", () => {
  const allLive = new Set(Object.values(LIVE_MEMBERS).flat());
  test("every key in TONE_MAP corresponds to a live enum member", () => {
    for (const key of Object.keys(TONE_MAP)) {
      expect(allLive).toContain(key);
    }
  });
});

// INV-75 guard: every wire value in LABEL_MAP produces a humanized label (not the raw key).
// If a member is dropped from LABEL_MAP this test fails — enforcement of D-60.
describe("INV-75 — LABEL_MAP: every wire value renders its authored label", () => {
  for (const [wireValue, expectedLabel] of Object.entries(LABEL_MAP)) {
    test(`"${wireValue}" renders "${expectedLabel}"`, () => {
      const { container } = render(<VerdictChip value={wireValue} />);
      expect((container.firstChild as HTMLElement).textContent).toBe(expectedLabel);
    });
  }

  test("unknown wire value falls back to raw value and calls console.warn", () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const { container } = render(<VerdictChip value="an_unknown_future_state" />);
    expect((container.firstChild as HTMLElement).textContent).toBe("an_unknown_future_state");
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("an_unknown_future_state")
    );
    warnSpy.mockRestore();
  });
});

describe("VerdictChip — renders chip per tone (via data-tone attribute)", () => {
  test("neutral member has data-tone=neutral", () => {
    const { container } = render(<VerdictChip value="draft" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("neutral");
  });

  test("progress member has data-tone=progress", () => {
    const { container } = render(<VerdictChip value="in_review" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("progress");
  });

  test("positive member has data-tone=positive", () => {
    const { container } = render(<VerdictChip value="approved" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("positive");
  });

  test("attention member has data-tone=attention", () => {
    const { container } = render(<VerdictChip value="needs_refresh" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("attention");
  });

  test("halt member has data-tone=halt", () => {
    const { container } = render(<VerdictChip value="halted_prohibited" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("halt");
  });

  test("terminal member has data-tone=terminal and line-through class", () => {
    const { container } = render(<VerdictChip value="retired" />);
    const chip = container.firstChild as HTMLElement;
    expect(chip.dataset.tone).toBe("terminal");
    expect(chip.className).toContain("line-through");
  });

  test("unknown wire value renders fallback chip with data-tone=unknown (no throw)", () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const { container } = render(<VerdictChip value="unknown_future_state" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("unknown");
    warnSpy.mockRestore();
  });
});

describe("VerdictChip — eu_ai_act_tier members render unknown fallback (D-48/INV-64)", () => {
  const TIER_MEMBERS = ["unclassified", "high", "limited", "minimal", "requires_context", "prohibited"];
  test.each(TIER_MEMBERS)("%s renders data-tone=unknown (not mapped in VerdictChip)", (member) => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const { container } = render(<VerdictChip value={member} />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("unknown");
    warnSpy.mockRestore();
  });
});

describe("VerdictChip — axe", () => {
  const sampleWireValues = ["draft", "in_review", "approved", "needs_refresh", "halted_prohibited", "retired"];
  test.each(sampleWireValues)("passes axe for %s", async (wireValue) => {
    const { container } = render(<VerdictChip value={wireValue} />);
    await expectNoAxeViolations(container);
  });
});
