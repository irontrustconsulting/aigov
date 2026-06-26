import { render } from "@testing-library/react";
import { PageHeader } from "../page-header";
import { PageScaffold } from "../page-scaffold";
import { expectNoAxeViolations } from "../../../test-utils/axe";

describe("PageHeader", () => {
  test("renders title as h1", () => {
    const { getByRole } = render(<PageHeader title="Portfolio" />);
    expect(getByRole("heading", { level: 1, name: "Portfolio" })).toBeInTheDocument();
  });

  test("renders subtitle when provided", () => {
    const { getByText } = render(
      <PageHeader title="Portfolio" subtitle="Your AI systems and assessments" />
    );
    expect(getByText("Your AI systems and assessments")).toBeInTheDocument();
  });

  test("does not render subtitle container when omitted", () => {
    const { queryByText } = render(<PageHeader title="Portfolio" />);
    expect(queryByText(/Your AI/)).not.toBeInTheDocument();
  });

  test("renders action slot", () => {
    const { getByRole } = render(
      <PageHeader title="Portfolio" action={<button>Register system</button>} />
    );
    expect(getByRole("button", { name: "Register system" })).toBeInTheDocument();
  });

  test("renders breadcrumb slot", () => {
    const { getByText } = render(
      <PageHeader title="Assessment" breadcrumb={<a href="/dashboard">Portfolio</a>} />
    );
    expect(getByText("Portfolio")).toBeInTheDocument();
  });
});

describe("PageScaffold", () => {
  test("wraps children in a max-w-4xl container", () => {
    const { container } = render(
      <PageScaffold>
        <p>Content</p>
      </PageScaffold>
    );
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("max-w-4xl");
  });

  test("snapshot — PageScaffold with PageHeader", () => {
    const { container } = render(
      <PageScaffold>
        <PageHeader title="Test Page" subtitle="A subtitle" />
      </PageScaffold>
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});

describe("PageHeader — onBack", () => {
  test("renders back button when onBack provided", () => {
    const onBack = jest.fn();
    const { getByRole } = render(<PageHeader title="Catalogue" onBack={onBack} />);
    expect(getByRole("button", { name: "Go back" })).toBeInTheDocument();
  });

  test("back button calls onBack when clicked", () => {
    const onBack = jest.fn();
    const { getByRole } = render(<PageHeader title="Catalogue" onBack={onBack} />);
    getByRole("button", { name: "Go back" }).click();
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  test("no back button when onBack omitted", () => {
    const { queryByRole } = render(<PageHeader title="Portfolio" />);
    expect(queryByRole("button", { name: "Go back" })).toBeNull();
  });

  test("with onBack — passes axe", async () => {
    const { container } = render(<PageHeader title="Catalogue" onBack={() => {}} />);
    await expectNoAxeViolations(container);
  });
});

describe("PageHeader — axe", () => {
  test("all four slots populated — passes axe", async () => {
    const { container } = render(
      <PageHeader
        title="Portfolio"
        subtitle="Your AI systems"
        action={<button>Register</button>}
        breadcrumb={<a href="/home">Home</a>}
      />
    );
    await expectNoAxeViolations(container);
  });

  test("title only — passes axe", async () => {
    const { container } = render(<PageHeader title="Portfolio" />);
    await expectNoAxeViolations(container);
  });
});
