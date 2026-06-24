import { render } from "@testing-library/react";
import { VerdictChip, TONE_MAP } from "../verdict-chip";
import { expectNoAxeViolations } from "../../../test-utils/axe";

/** Live members per V-5 pg_enum dump. Any new member added to the DB must
 * appear here and in TONE_MAP — the test will catch the gap. */
const LIVE_MEMBERS: Record<string, string[]> = {
  assessment_status: ["APPROVED", "DRAFT", "IN_REVIEW", "NEEDS_REFRESH"],
  lifecycle_state: [
    "AUTHORISED", "DEPLOYED", "HALTED_PROHIBITED", "HELD", "INTAKE",
    "PENDING_AUTHORISATION", "PRODUCT_CHECK", "REQUESTED", "RETIRED",
    "TREATMENT_PENDING", "UNDER_ASSESSMENT", "VENDOR_CHECK",
  ],
  eu_ai_act_tier: ["HIGH", "LIMITED", "MINIMAL", "PROHIBITED", "REQUIRES_CONTEXT", "UNCLASSIFIED"],
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

describe("VerdictChip — renders chip per tone (via data-tone attribute)", () => {
  test("neutral member has data-tone=neutral", () => {
    const { container } = render(<VerdictChip value="DRAFT" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("neutral");
  });

  test("progress member has data-tone=progress", () => {
    const { container } = render(<VerdictChip value="IN_REVIEW" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("progress");
  });

  test("positive member has data-tone=positive", () => {
    const { container } = render(<VerdictChip value="APPROVED" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("positive");
  });

  test("attention member has data-tone=attention", () => {
    const { container } = render(<VerdictChip value="NEEDS_REFRESH" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("attention");
  });

  test("halt member has data-tone=halt", () => {
    const { container } = render(<VerdictChip value="HALTED_PROHIBITED" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("halt");
  });

  test("terminal member has data-tone=terminal and line-through class", () => {
    const { container } = render(<VerdictChip value="RETIRED" />);
    const chip = container.firstChild as HTMLElement;
    expect(chip.dataset.tone).toBe("terminal");
    expect(chip.className).toContain("line-through");
  });

  test("unknown member renders fallback chip with data-tone=unknown (no throw)", () => {
    const { container } = render(<VerdictChip value="UNKNOWN_FUTURE_STATE" />);
    expect((container.firstChild as HTMLElement).dataset.tone).toBe("unknown");
  });
});

describe("VerdictChip — axe", () => {
  const sampleMembers = ["DRAFT", "IN_REVIEW", "APPROVED", "NEEDS_REFRESH", "HALTED_PROHIBITED", "RETIRED"];
  test.each(sampleMembers)("passes axe for %s", async (member) => {
    const { container } = render(<VerdictChip value={member} />);
    await expectNoAxeViolations(container);
  });
});
