import { render } from "@testing-library/react";
import { DraftResumeIndicator } from "../draft-resume-indicator";
import { DraftResumeIndicator as DraftResumeIndicatorFromKit } from "../../kit";
import { DraftResumeIndicator as DraftResumeIndicatorFromRoot } from "../../../src";
import { expectNoAxeViolations } from "../../../test-utils/axe";

const baseProps = {
  productLabel: "ATS Pro",
  href: "/systems/new",
};

describe("DraftResumeIndicator (FE-29)", () => {
  test("renders the resume link to the passed href with label 'Resume'", () => {
    const { getByRole } = render(<DraftResumeIndicator {...baseProps} />);
    const link = getByRole("link", { name: /Resume/ });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/systems/new");
  });

  test("renders productLabel when provided", () => {
    const { getByText } = render(<DraftResumeIndicator {...baseProps} />);
    expect(getByText("ATS Pro")).toBeInTheDocument();
  });

  test("renders 'Untitled registration' when productLabel is null", () => {
    const { getByText } = render(
      <DraftResumeIndicator {...baseProps} productLabel={null} />
    );
    expect(getByText("Untitled registration")).toBeInTheDocument();
  });

  test("resume affordance is an anchor element, not a div with onClick", () => {
    const { getByRole } = render(<DraftResumeIndicator {...baseProps} />);
    const link = getByRole("link", { name: /Resume/ });
    expect(link.tagName).toBe("A");
  });

  test("passes axe", async () => {
    const { container } = render(<DraftResumeIndicator {...baseProps} />);
    await expectNoAxeViolations(container);
  });

  test("exported from kit/index.ts", () => {
    expect(DraftResumeIndicatorFromKit).toBeDefined();
  });

  test("exported from root index.ts", () => {
    expect(DraftResumeIndicatorFromRoot).toBeDefined();
  });
});
