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

  // FE-33 ALTER assertions

  test("label renders in the header", () => {
    render(
      <PrefillWithBasis
        label="DPA available"
        valueLabel="Yes"
        basis="Vendor documentation"
        provenance="catalogue_curated"
        options={options}
        onOverride={jest.fn()}
      />
    );
    expect(screen.getByText("DPA available")).toBeInTheDocument();
  });

  test("badge is a sibling of label in the header row, not adjacent to the value", () => {
    const { container } = render(
      <PrefillWithBasis
        label="DPA available"
        valueLabel="not-this"
        valueContent={<span data-testid="value-node">Yes chip here</span>}
        basis="Vendor documentation"
        provenance="catalogue_curated"
        options={options}
        onOverride={jest.fn()}
      />
    );
    // The header row is the first child div.
    const headerRow = container.querySelector("div.space-y-2 > div");
    expect(headerRow).toBeInTheDocument();
    // Badge renders inside the header row.
    const badge = headerRow!.querySelector("[data-provenance]") ?? headerRow!.querySelector("span");
    expect(badge).toBeInTheDocument();
    // The value node is NOT inside the header row.
    const valueNode = headerRow!.querySelector("[data-testid='value-node']");
    expect(valueNode).toBeNull();
    // The value node IS in the card but outside the header row.
    expect(container.querySelector("[data-testid='value-node']")).toBeInTheDocument();
  });

  test("valueContent node renders when passed", () => {
    render(
      <PrefillWithBasis
        label="Certifications"
        valueLabel="fallback"
        valueContent={<span data-testid="typed-value">SOC 2 pill here</span>}
        basis="Vendor documentation"
        provenance="catalogue_curated"
        options={options}
        onOverride={jest.fn()}
      />
    );
    expect(screen.getByTestId("typed-value")).toBeInTheDocument();
    expect(screen.queryByText("fallback")).not.toBeInTheDocument();
  });

  test("omitting valueContent renders valueLabel unchanged (back-compat)", () => {
    render(
      <PrefillWithBasis
        valueLabel="High"
        basis="Derived from product category"
        provenance="ai_suggested"
        options={options}
        onOverride={jest.fn()}
      />
    );
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  test("onOverride signature carries no provenance param (INV-55, retained)", () => {
    const onOverride = jest.fn();
    render(
      <PrefillWithBasis
        label="Hosting region"
        valueLabel="EU"
        basis="Catalogue"
        provenance="catalogue_curated"
        options={[{ value: "not_applicable", label: "Not applicable" }]}
        onOverride={onOverride}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Override" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm override" }));
    expect(onOverride).toHaveBeenCalledTimes(1);
    // Payload is (value, justification?) — no provenance value in either arg
    const call = onOverride.mock.calls[0] as unknown[];
    expect(call[0]).toBe("not_applicable");
    // Second arg is undefined (empty justification), never a provenance string
    expect(call[1]).toBeUndefined();
  });
});
