import { render, fireEvent } from "@testing-library/react";
import { EmptyState } from "../empty-state";
import { FirstRunPanel } from "../first-run-panel";
import { ErrorState } from "../error-state";
import { Skeleton, SkeletonBlock } from "../skeleton";
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

describe("ErrorState", () => {
  test("renders message and Try again button", () => {
    const { getByText, getByRole } = render(
      <ErrorState message="Could not load portfolio." onRetry={jest.fn()} />
    );
    expect(getByText("Could not load portfolio.")).toBeInTheDocument();
    expect(getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("calls onRetry when Try again clicked", () => {
    const onRetry = jest.fn();
    const { getByRole } = render(
      <ErrorState message="Error." onRetry={onRetry} />
    );
    fireEvent.click(getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  test("renders optional supportLine", () => {
    const { getByText } = render(
      <ErrorState
        message="Error."
        onRetry={jest.fn()}
        supportLine="Please contact support."
      />
    );
    expect(getByText("Please contact support.")).toBeInTheDocument();
  });

  test("does not render supportLine when absent", () => {
    const { queryByText } = render(
      <ErrorState message="Error." onRetry={jest.fn()} />
    );
    expect(queryByText("Please contact support.")).toBeNull();
  });

  test("snapshot — without supportLine", () => {
    const { container } = render(
      <ErrorState message="Could not load data." onRetry={jest.fn()} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  test("snapshot — with supportLine", () => {
    const { container } = render(
      <ErrorState
        message="Could not load data."
        onRetry={jest.fn()}
        supportLine="If the problem persists, contact support."
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});

describe("ErrorState — axe", () => {
  test("passes axe", async () => {
    const { container } = render(
      <ErrorState message="Could not load portfolio." onRetry={jest.fn()} />
    );
    await expectNoAxeViolations(container);
  });

  test("with supportLine — passes axe", async () => {
    const { container } = render(
      <ErrorState
        message="Could not load portfolio."
        onRetry={jest.fn()}
        supportLine="Please try again later."
      />
    );
    await expectNoAxeViolations(container);
  });
});

describe("Skeleton", () => {
  test("renders default 3 placeholder blocks", () => {
    const { container } = render(<Skeleton />);
    // role=status present
    expect(container.querySelector("[role='status']")).toBeInTheDocument();
    // 3 children inside the status div
    const blocks = container.querySelectorAll("[aria-hidden='true']");
    expect(blocks).toHaveLength(3);
  });

  test("renders specified number of lines", () => {
    const { container } = render(<Skeleton lines={5} />);
    const blocks = container.querySelectorAll("[aria-hidden='true']");
    expect(blocks).toHaveLength(5);
  });

  test("snapshot — default", () => {
    const { container } = render(<Skeleton />);
    expect(container.firstChild).toMatchSnapshot();
  });

  test("snapshot — 5 lines", () => {
    const { container } = render(<Skeleton lines={5} />);
    expect(container.firstChild).toMatchSnapshot();
  });
});

describe("SkeletonBlock", () => {
  test("renders single block with aria-hidden", () => {
    const { container } = render(<SkeletonBlock className="h-8 w-full" />);
    expect(container.querySelector("[aria-hidden='true']")).toBeInTheDocument();
  });
});

describe("Skeleton — axe", () => {
  test("passes axe", async () => {
    const { container } = render(<Skeleton lines={3} />);
    await expectNoAxeViolations(container);
  });
});
