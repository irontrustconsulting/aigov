import { render } from "@testing-library/react";
import { Sidebar } from "../sidebar";
import { expectNoAxeViolations } from "../../../test-utils/axe";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Portfolio", isActive: true },
  { href: "/evidence", label: "Evidence", isActive: false },
];

describe("Sidebar", () => {
  test("renders brand, nav items and foot", () => {
    const { getByText, getByRole } = render(
      <Sidebar
        brand={<a href="/dashboard">IronTrust</a>}
        navItems={NAV_ITEMS}
        foot={<p>User Name</p>}
      />
    );
    expect(getByText("IronTrust")).toBeInTheDocument();
    expect(getByText("Portfolio")).toBeInTheDocument();
    expect(getByText("Evidence")).toBeInTheDocument();
    expect(getByText("User Name")).toBeInTheDocument();
    expect(getByRole("navigation")).toBeInTheDocument();
  });

  test("active item carries aria-current=page", () => {
    const { getByText } = render(
      <Sidebar
        brand={<a href="/">IronTrust</a>}
        navItems={NAV_ITEMS}
        foot={<span />}
      />
    );
    expect(getByText("Portfolio").closest("a")).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(getByText("Evidence").closest("a")).not.toHaveAttribute(
      "aria-current"
    );
  });

  test("inactive item does not carry aria-current", () => {
    const { getByText } = render(
      <Sidebar
        brand={<a href="/">IronTrust</a>}
        navItems={NAV_ITEMS}
        foot={<span />}
      />
    );
    expect(getByText("Evidence").closest("a")).not.toHaveAttribute(
      "aria-current"
    );
  });

  test("railBg sets inline background style on aside", () => {
    const { container } = render(
      <Sidebar
        brand={<a href="/">IronTrust</a>}
        navItems={[]}
        foot={<span />}
        railBg="var(--chrome-rail-bg)"
      />
    );
    const aside = container.querySelector("aside");
    expect(aside).toHaveStyle({ backgroundColor: "var(--chrome-rail-bg)" });
  });

  test("nav slot overrides navItems", () => {
    const { queryByText, getByText } = render(
      <Sidebar
        brand={<a href="/">IronTrust</a>}
        nav={<nav><a href="/custom">Custom</a></nav>}
        navItems={NAV_ITEMS}
        foot={<span />}
      />
    );
    expect(getByText("Custom")).toBeInTheDocument();
    expect(queryByText("Portfolio")).not.toBeInTheDocument();
  });
});

describe("Sidebar — axe", () => {
  test("tenant variant passes axe", async () => {
    const { container } = render(
      <Sidebar
        brand={<a href="/dashboard">IronTrust</a>}
        navItems={NAV_ITEMS}
        foot={<p>User Name</p>}
      />
    );
    await expectNoAxeViolations(container);
  });

  test("operator rail variant passes axe", async () => {
    const { container } = render(
      <Sidebar
        brand={<a href="/">IronTrust</a>}
        nav={
          <nav aria-label="Operator console navigation">
            <ul role="list">
              <li><a href="/provisioning" aria-current="page">Provisioning</a></li>
            </ul>
          </nav>
        }
        railBg="var(--chrome-rail-bg)"
        foot={<p>operator@example.com</p>}
      />
    );
    await expectNoAxeViolations(container);
  });
});
