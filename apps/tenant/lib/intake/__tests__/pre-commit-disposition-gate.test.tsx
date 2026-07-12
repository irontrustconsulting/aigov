/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { PreCommitDispositionGate, type DerivedDispositionItem } from "../pre-commit-disposition-gate";

const operatorRoleOptions = [
  { value: "role-deployer", label: "Deployer" },
  { value: "role-provider", label: "Provider" },
];

function items(overrides?: Partial<DerivedDispositionItem>[]): DerivedDispositionItem[] {
  const base: DerivedDispositionItem[] = [
    {
      field: "operatorRoleId",
      label: "Operator role",
      value: "role-deployer",
      options: operatorRoleOptions,
      confirmed: false,
    },
    {
      field: "lifecycleStage",
      label: "Lifecycle stage",
      value: "production",
      options: [{ value: "production", label: "Production" }],
      confirmed: true,
    },
  ];
  if (!overrides) return base;
  return base.map((b, i) => ({ ...b, ...overrides[i] }));
}

describe("PreCommitDispositionGate (FE-36, E-compact, Path B)", () => {
  test("hidden when the unconfirmed set is empty", () => {
    const allConfirmed = items().map((i) => ({ ...i, confirmed: true }));
    const { container } = render(
      <PreCommitDispositionGate
        derivedItems={allConfirmed}
        onConfirm={jest.fn()}
        onChange={jest.fn()}
        factCount={3}
        onReviewFacts={jest.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  test("hidden when derivedItems is empty (no derived fields at all)", () => {
    const { container } = render(
      <PreCommitDispositionGate
        derivedItems={[]}
        onConfirm={jest.fn()}
        onChange={jest.fn()}
        factCount={0}
        onReviewFacts={jest.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  test("renders both the unconfirmed item and an already-confirmed item with its indicator", () => {
    render(
      <PreCommitDispositionGate
        derivedItems={items()}
        onConfirm={jest.fn()}
        onChange={jest.fn()}
        factCount={0}
        onReviewFacts={jest.fn()}
      />
    );
    expect(screen.getByText("Operator role")).toBeInTheDocument();
    expect(screen.getByText("Derived, confirm or update")).toBeInTheDocument();
    expect(screen.getByText("Derived, confirmed")).toBeInTheDocument();
  });

  test("Confirm fires onConfirm(field)", () => {
    const onConfirm = jest.fn();
    render(
      <PreCommitDispositionGate
        derivedItems={items()}
        onConfirm={onConfirm}
        onChange={jest.fn()}
        factCount={0}
        onReviewFacts={jest.fn()}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).toHaveBeenCalledWith("operatorRoleId");
  });

  test("Change reveals the field's select and picking a value fires onChange", () => {
    const onChange = jest.fn();
    render(
      <PreCommitDispositionGate
        derivedItems={items()}
        onConfirm={jest.fn()}
        onChange={onChange}
        factCount={0}
        onReviewFacts={jest.fn()}
      />
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Change" })[0]!);
    const select = screen.getByLabelText("Operator role");
    fireEvent.change(select, { target: { value: "role-provider" } });
    expect(onChange).toHaveBeenCalledWith("operatorRoleId", "role-provider");
  });

  test("facts recap renders factCount and never asserts fact confirmation", () => {
    render(
      <PreCommitDispositionGate
        derivedItems={items()}
        onConfirm={jest.fn()}
        onChange={jest.fn()}
        factCount={12}
        onReviewFacts={jest.fn()}
      />
    );
    expect(screen.getByText(/12 catalogue facts have not been reviewed this session/)).toBeInTheDocument();
    expect(screen.queryByText(/confirmed/i, { selector: "*" })?.textContent ?? "").not.toMatch(/fact/i);
    // Path B: never claims facts were confirmed
    const html = document.body.innerHTML;
    expect(html).not.toMatch(/facts?\s+(have been|were)\s+confirmed/i);
  });

  test("Review-facts link fires onReviewFacts", () => {
    const onReviewFacts = jest.fn();
    render(
      <PreCommitDispositionGate
        derivedItems={items()}
        onConfirm={jest.fn()}
        onChange={jest.fn()}
        factCount={5}
        onReviewFacts={onReviewFacts}
      />
    );
    fireEvent.click(screen.getByText("Review facts ›"));
    expect(onReviewFacts).toHaveBeenCalled();
  });

  test("facts recap has no gating effect: hidden with factCount=0, but still shown when derived items are unconfirmed", () => {
    render(
      <PreCommitDispositionGate
        derivedItems={items()}
        onConfirm={jest.fn()}
        onChange={jest.fn()}
        factCount={0}
        onReviewFacts={jest.fn()}
      />
    );
    expect(screen.getByText("Operator role")).toBeInTheDocument();
    expect(screen.queryByText(/catalogue facts have not been reviewed/)).not.toBeInTheDocument();
  });

  test("rendered DOM carries no --verdict-* class and no border-brand", () => {
    const { container } = render(
      <PreCommitDispositionGate
        derivedItems={items()}
        onConfirm={jest.fn()}
        onChange={jest.fn()}
        factCount={5}
        onReviewFacts={jest.fn()}
      />
    );
    const html = container.innerHTML;
    expect(html).not.toMatch(/--verdict-/);
    expect(html).not.toMatch(/border-brand/);
  });
});
