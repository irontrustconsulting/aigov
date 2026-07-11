import { render, fireEvent } from "@testing-library/react";
import { ResumePrompt } from "../resume-prompt";
import { expectNoAxeViolations } from "../../../test-utils/axe";

const baseProps = {
  productName: "ATS Pro",
  savedStep: "intake",
  lastEditedAt: "2026-06-27T12:00:00Z",
  onResume: jest.fn(),
  onDiscard: jest.fn(),
};

describe("ResumePrompt (FE-28)", () => {
  beforeEach(() => jest.clearAllMocks());

  test("renders product name in heading", () => {
    const { getByText } = render(<ResumePrompt {...baseProps} />);
    expect(getByText(/Continue registering ATS Pro/)).toBeInTheDocument();
  });

  test("falls back to generic text when productName is null", () => {
    const { getByText } = render(
      <ResumePrompt {...baseProps} productName={null} />
    );
    expect(getByText(/Continue registering your AI system/)).toBeInTheDocument();
  });

  test("renders saved step label", () => {
    const { getByText } = render(<ResumePrompt {...baseProps} />);
    expect(getByText(/Step: intake/)).toBeInTheDocument();
  });

  test("Resume button calls onResume", () => {
    const onResume = jest.fn();
    const { getByRole } = render(
      <ResumePrompt {...baseProps} onResume={onResume} />
    );
    fireEvent.click(getByRole("button", { name: "Resume" }));
    expect(onResume).toHaveBeenCalledTimes(1);
  });

  test("Discard button reveals an inline confirm instead of firing onDiscard immediately", () => {
    const onDiscard = jest.fn();
    const { getByRole, getByText } = render(
      <ResumePrompt {...baseProps} onDiscard={onDiscard} />
    );
    fireEvent.click(getByRole("button", { name: "Discard" }));
    expect(onDiscard).not.toHaveBeenCalled();
    expect(
      getByText("Discard this registration and start fresh? This cannot be undone.")
    ).toBeInTheDocument();
  });

  test("confirm's Discard calls onDiscard once", () => {
    const onDiscard = jest.fn();
    const { getByRole } = render(
      <ResumePrompt {...baseProps} onDiscard={onDiscard} />
    );
    fireEvent.click(getByRole("button", { name: "Discard" }));
    fireEvent.click(getByRole("button", { name: "Discard" }));
    expect(onDiscard).toHaveBeenCalledTimes(1);
  });

  test("Cancel dismisses the confirm without calling onDiscard", () => {
    const onDiscard = jest.fn();
    const { getByRole, queryByText } = render(
      <ResumePrompt {...baseProps} onDiscard={onDiscard} />
    );
    fireEvent.click(getByRole("button", { name: "Discard" }));
    fireEvent.click(getByRole("button", { name: "Cancel" }));
    expect(onDiscard).not.toHaveBeenCalled();
    expect(
      queryByText("Discard this registration and start fresh? This cannot be undone.")
    ).not.toBeInTheDocument();
    expect(getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });

  test("passes axe", async () => {
    const { container } = render(<ResumePrompt {...baseProps} />);
    await expectNoAxeViolations(container);
  });
});
