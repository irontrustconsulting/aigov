import { render, screen } from "@testing-library/react";
import { TierBadge } from "../tier-badge";
import { expectNoAxeViolations } from "../../../test-utils/axe";

const ALL_MEMBERS = [
  "PROHIBITED",
  "HIGH",
  "LIMITED",
  "MINIMAL",
  "UNCLASSIFIED",
  "REQUIRES_CONTEXT",
] as const;

const MAGNITUDE_MEMBERS = ["PROHIBITED", "HIGH", "LIMITED", "MINIMAL"] as const;
const RESOLUTION_MEMBERS = ["UNCLASSIFIED", "REQUIRES_CONTEXT"] as const;

describe("TierBadge compact — data-tier attribute per member", () => {
  for (const member of ALL_MEMBERS) {
    test(`${member} renders data-tier="${member.toLowerCase()}"`, () => {
      const { container } = render(<TierBadge value={member} />);
      const el = container.firstChild as HTMLElement;
      expect(el.dataset.tier).toBe(member.toLowerCase());
      expect(el.dataset.variant).toBe("compact");
    });
  }
});

describe("TierBadge compact — PROHIBITED has Ban icon", () => {
  test("PROHIBITED renders svg Ban icon", () => {
    const { container } = render(<TierBadge value="PROHIBITED" />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
  });

  test.each(["HIGH", "LIMITED", "MINIMAL", "UNCLASSIFIED", "REQUIRES_CONTEXT"] as const)(
    "%s does not render an icon",
    (member) => {
      const { container } = render(<TierBadge value={member} />);
      expect(container.querySelector("svg")).toBeNull();
    }
  );
});

describe("TierBadge compact — magnitude tiers use --tier-* channel", () => {
  test.each(MAGNITUDE_MEMBERS)("%s has data-tier-channel=tier", (member) => {
    const { container } = render(<TierBadge value={member} />);
    const el = container.firstChild as HTMLElement;
    expect(el.dataset.tierChannel).toBe("tier");
  });
});

describe("TierBadge compact — resolution states use --verdict-* channel", () => {
  test.each(RESOLUTION_MEMBERS)("%s has data-tier-channel=verdict", (member) => {
    const { container } = render(<TierBadge value={member} />);
    const el = container.firstChild as HTMLElement;
    expect(el.dataset.tierChannel).toBe("verdict");
  });
});

describe("TierBadge card — renders slots", () => {
  test("card variant renders with data-variant=card", () => {
    const { container } = render(<TierBadge value="HIGH" variant="card" />);
    const el = container.firstChild as HTMLElement;
    expect(el.dataset.variant).toBe("card");
  });

  test("card renders basis slot when provided", () => {
    render(<TierBadge value="HIGH" variant="card" basis={<p>Annex III §2</p>} />);
    expect(screen.getByText("Annex III §2")).toBeInTheDocument();
  });

  test("card renders overrideLadder slot when provided", () => {
    render(
      <TierBadge
        value="HIGH"
        variant="card"
        overrideLadder={<button>Override</button>}
      />
    );
    expect(screen.getByRole("button", { name: "Override" })).toBeInTheDocument();
  });

  test("card renders without overrideLadder when not provided", () => {
    render(<TierBadge value="HIGH" variant="card" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  test("PROHIBITED card renders Ban icon", () => {
    const { container } = render(<TierBadge value="PROHIBITED" variant="card" />);
    expect(container.querySelector("svg")).not.toBeNull();
  });
});

describe("TierBadge — axe zero violations", () => {
  const compactCases = ALL_MEMBERS;
  test.each(compactCases)("compact %s passes axe", async (member) => {
    const { container } = render(<TierBadge value={member} />);
    await expectNoAxeViolations(container);
  });

  test("card HIGH with basis + overrideLadder passes axe", async () => {
    const { container } = render(
      <TierBadge
        value="HIGH"
        variant="card"
        basis={<p>Legal basis text</p>}
        overrideLadder={<button>Override</button>}
      />
    );
    await expectNoAxeViolations(container);
  });
});
