import { render } from "@testing-library/react";
import { EmptyState } from "../empty-state";
import { FirstRunPanel } from "../first-run-panel";
import { expectNoAxeViolations } from "../../../test-utils/axe";

describe("EmptyState", () => {
  test("renders message", () => {
    const { getByText } = render(
      <EmptyState message="No systems registered yet." />
    );
    expect(getByText("No systems registered yet.")).toBeInTheDocument();
  });

  test("renders optional icon", () => {
    const { getByText } = render(
      <EmptyState icon={<span>📭</span>} message="Nothing here." />
    );
    expect(getByText("📭")).toBeInTheDocument();
  });

  test("renders optional action", () => {
    const { getByRole } = render(
      <EmptyState
        message="Nothing here."
        action={<button>Register a system</button>}
      />
    );
    expect(getByRole("button", { name: "Register a system" })).toBeInTheDocument();
  });

  test("renders as role=status", () => {
    const { getByRole } = render(<EmptyState message="Empty." />);
    expect(getByRole("status")).toBeInTheDocument();
  });

  test("snapshot", () => {
    const { container } = render(
      <EmptyState
        icon={<span>📭</span>}
        message="No items found."
        action={<button>Add item</button>}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});

describe("FirstRunPanel", () => {
  test("renders heading and body", () => {
    const { getByRole, getByText } = render(
      <FirstRunPanel
        heading="Get started"
        body="Register your first AI system to begin."
        action={<button>Register</button>}
      />
    );
    expect(getByRole("heading", { level: 2, name: "Get started" })).toBeInTheDocument();
    expect(getByText("Register your first AI system to begin.")).toBeInTheDocument();
  });

  test("renders action", () => {
    const { getByRole } = render(
      <FirstRunPanel
        heading="Get started"
        body="Register your first AI system."
        action={<button>Register</button>}
      />
    );
    expect(getByRole("button", { name: "Register" })).toBeInTheDocument();
  });

  test("snapshot", () => {
    const { container } = render(
      <FirstRunPanel
        heading="Get started"
        body="Register your first AI system to begin."
        action={<button>Register</button>}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});

describe("EmptyState — axe", () => {
  test("with all props — passes axe", async () => {
    const { container } = render(
      <EmptyState
        icon={<span aria-hidden="true">○</span>}
        message="No items."
        action={<button>Add item</button>}
      />
    );
    await expectNoAxeViolations(container);
  });

  test("message only — passes axe", async () => {
    const { container } = render(<EmptyState message="No items." />);
    await expectNoAxeViolations(container);
  });
});

describe("FirstRunPanel — axe", () => {
  test("passes axe", async () => {
    const { container } = render(
      <FirstRunPanel
        heading="Get started"
        body="Register your first AI system."
        action={<button>Register</button>}
      />
    );
    await expectNoAxeViolations(container);
  });
});
