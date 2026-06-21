import { render, screen, fireEvent } from "@testing-library/react";
import { PrefillWithBasis } from "../prefill-with-basis";
import { expectNoAxeViolations } from "../../../test-utils/axe";

const options = [
  { value: "HIGH", label: "High" },
  { value: "LIMITED", label: "Limited" },
];

describe("PrefillWithBasis", () => {
  test("renders the server-supplied provenance value verbatim", () => {
    render(
      <PrefillWithBasis
        valueLabel="High"
        basis="Derived from product category"
        provenance="ai_suggested"
        options={options}
        onOverride={jest.fn()}
      />
    );
    expect(screen.getByText("AI suggested")).toBeInTheDocument();
    expect(screen.getByText("Derived from product category")).toBeInTheDocument();
  });

  test("override submit never includes a provenance key in the payload", () => {
    const onOverride = jest.fn();
    render(
      <PrefillWithBasis
        valueLabel="High"
        basis="Derived from product category"
        provenance="ai_suggested"
        options={options}
        onOverride={onOverride}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Override" }));
    fireEvent.change(screen.getByLabelText("New value"), { target: { value: "LIMITED" } });
    fireEvent.change(screen.getByLabelText("Justification (optional)"), {
      target: { value: "Reassessed scope" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm override" }));

    expect(onOverride).toHaveBeenCalledWith("LIMITED", "Reassessed scope");
    // The callback signature itself carries no provenance parameter — the
    // component has no code path that could construct one.
    const [, ...rest] = onOverride.mock.calls[0];
    expect(rest).not.toContain("provenance");
  });

  test("passes axe with no violations, including the override panel open", async () => {
    const { container } = render(
      <PrefillWithBasis
        valueLabel="High"
        basis="Derived from product category"
        provenance="user_confirmed"
        options={options}
        onOverride={jest.fn()}
      />
    );
    await expectNoAxeViolations(container);

    fireEvent.click(screen.getByRole("button", { name: "Override" }));
    await expectNoAxeViolations(container);
  });
});
