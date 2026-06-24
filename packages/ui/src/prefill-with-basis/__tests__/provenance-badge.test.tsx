import { render, screen } from "@testing-library/react";
import { ProvenanceBadge, type Provenance, PROV_BORDER_COLOR } from "../provenance-badge";
import { expectNoAxeViolations } from "../../../test-utils/axe";

const ALL_MEMBERS: Provenance[] = [
  "ai_suggested",
  "catalogue_curated",
  "user_confirmed",
  "user_amended",
];

describe("ProvenanceBadge — one case per enum member", () => {
  test("ai_suggested: renders with dashed border and ink label", () => {
    const { container } = render(<ProvenanceBadge provenance="ai_suggested" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("border-dashed");
    expect(badge.className).toContain("text-ink");
    expect(screen.getByText("AI suggested")).toBeInTheDocument();
  });

  test("catalogue_curated: renders with solid border and ink label", () => {
    const { container } = render(<ProvenanceBadge provenance="catalogue_curated" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("border-solid");
    expect(badge.className).toContain("text-ink");
    expect(screen.getByText("Catalogue")).toBeInTheDocument();
  });

  test("user_confirmed: renders with solid border and ink label", () => {
    const { container } = render(<ProvenanceBadge provenance="user_confirmed" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("border-solid");
    expect(badge.className).toContain("text-ink");
    expect(screen.getByText("Confirmed")).toBeInTheDocument();
  });

  test("user_amended: renders with solid border and ink label", () => {
    const { container } = render(<ProvenanceBadge provenance="user_amended" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("border-solid");
    expect(badge.className).toContain("text-ink");
    expect(screen.getByText("Amended")).toBeInTheDocument();
  });
});

describe("ProvenanceBadge — no 5th member (V-2 guard)", () => {
  test("PROV_BORDER_COLOR has exactly 4 keys — no USER_PROVIDED branch", () => {
    expect(Object.keys(PROV_BORDER_COLOR)).toHaveLength(4);
    expect(PROV_BORDER_COLOR).not.toHaveProperty("user_provided");
  });

  test("every key in PROV_BORDER_COLOR references a CSS var(), not a literal hex", () => {
    for (const value of Object.values(PROV_BORDER_COLOR)) {
      expect(value).toMatch(/^var\(--prov-/);
    }
  });
});

describe("ProvenanceBadge — axe", () => {
  test.each(ALL_MEMBERS)("passes axe for %s", async (provenance) => {
    const { container } = render(<ProvenanceBadge provenance={provenance} />);
    await expectNoAxeViolations(container);
  });
});
