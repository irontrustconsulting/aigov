import { render } from "@testing-library/react";
import { WhoseCourtIndicator } from "../whose-court-indicator";
import { expectNoAxeViolations } from "../../../test-utils/axe";

describe("WhoseCourtIndicator", () => {
  test("isYourCourt=true: data-court=yours", () => {
    const { container } = render(
      <WhoseCourtIndicator partyLabel="Risk Owner" isYourCourt={true} />
    );
    expect((container.firstChild as HTMLElement).dataset.court).toBe("yours");
  });

  test("isYourCourt=false: data-court=theirs, neutral classes", () => {
    const { container } = render(
      <WhoseCourtIndicator partyLabel="Compliance Team" isYourCourt={false} />
    );
    const el = container.firstChild as HTMLElement;
    expect(el.dataset.court).toBe("theirs");
    expect(el.className).toContain("bg-surface-sunken");
    expect(el.className).toContain("text-ink-muted");
  });

  test("yours and theirs are distinguishable by data-court attribute", () => {
    const { container: c1 } = render(
      <WhoseCourtIndicator partyLabel="A" isYourCourt={true} />
    );
    const { container: c2 } = render(
      <WhoseCourtIndicator partyLabel="B" isYourCourt={false} />
    );
    expect((c1.firstChild as HTMLElement).dataset.court).toBe("yours");
    expect((c2.firstChild as HTMLElement).dataset.court).toBe("theirs");
  });
});

describe("WhoseCourtIndicator — axe", () => {
  test("yours — passes axe", async () => {
    const { container } = render(
      <WhoseCourtIndicator partyLabel="Risk Owner" isYourCourt={true} />
    );
    await expectNoAxeViolations(container);
  });
  test("theirs — passes axe", async () => {
    const { container } = render(
      <WhoseCourtIndicator partyLabel="Compliance" isYourCourt={false} />
    );
    await expectNoAxeViolations(container);
  });
});
