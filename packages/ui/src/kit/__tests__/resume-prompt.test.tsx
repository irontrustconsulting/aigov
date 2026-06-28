import { render, fireEvent } from "@testing-library/react";
import { ResumePrompt } from "../resume-prompt";
import { expectNoAxeViolations } from "../../../test-utils/axe";

const baseProps = {
  productName: "ATS Pro",
  savedStep: "intake",
  lastEditedAt: "2026-06-27T12:00:00Z",
  onResume: jest.fn(),
  onStartOver: jest.fn(),
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

  test("Start over button calls onStartOver", () => {
    const onStartOver = jest.fn();
    const { getByRole } = render(
      <ResumePrompt {...baseProps} onStartOver={onStartOver} />
    );
    fireEvent.click(getByRole("button", { name: "Start over" }));
    expect(onStartOver).toHaveBeenCalledTimes(1);
  });

  test("passes axe", async () => {
    const { container } = render(<ResumePrompt {...baseProps} />);
    await expectNoAxeViolations(container);
  });
});
