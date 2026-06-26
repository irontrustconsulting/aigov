import { render } from "@testing-library/react";
import { TableCell, TableHeaderCell, TableRow } from "../../primitives/table";
import { StatCard } from "../stat-card";
import { SectionHeader } from "../section-header";
import { ListSelectRow } from "../list-select-row";
import { LogoTile } from "../logo-tile";
import { DataTable, DataTableHeader, DataTableBody } from "../data-table";
import { expectNoAxeViolations } from "../../../test-utils/axe";

// ── StatCard ──────────────────────────────────────────────────────────────────

describe("StatCard", () => {
  test("renders label and value", () => {
    const { getByText } = render(<StatCard label="Systems" value={4} />);
    expect(getByText("Systems")).toBeInTheDocument();
    expect(getByText("4")).toBeInTheDocument();
  });

  test("renders optional trend slot", () => {
    const { getByText } = render(
      <StatCard label="Systems" value={4} trend={<span>↑ 2</span>} />
    );
    expect(getByText("↑ 2")).toBeInTheDocument();
  });

  test("passes axe", async () => {
    const { container } = render(<StatCard label="Systems" value={4} />);
    await expectNoAxeViolations(container);
  });
});

// ── SectionHeader ─────────────────────────────────────────────────────────────

describe("SectionHeader", () => {
  test("renders title as h2", () => {
    const { getByRole } = render(<SectionHeader title="Systems" />);
    expect(getByRole("heading", { level: 2, name: "Systems" })).toBeInTheDocument();
  });

  test("renders optional action slot", () => {
    const { getByRole } = render(
      <SectionHeader title="Systems" action={<button>Add</button>} />
    );
    expect(getByRole("button", { name: "Add" })).toBeInTheDocument();
  });

  test("passes axe", async () => {
    const { container } = render(
      <SectionHeader title="Systems" action={<button>Add</button>} />
    );
    await expectNoAxeViolations(container);
  });
});

// ── ListSelectRow ─────────────────────────────────────────────────────────────

describe("ListSelectRow", () => {
  test("renders as a button with the label", () => {
    const { getByRole } = render(
      <ListSelectRow label="Customer Engagement" onClick={() => {}} />
    );
    expect(getByRole("button", { name: /Customer Engagement/ })).toBeInTheDocument();
  });

  test("has exactly one ChevronRight icon and label text", () => {
    const { container, getByText } = render(
      <ListSelectRow label="Customer Engagement" onClick={() => {}} />
    );
    const svgs = container.querySelectorAll("svg");
    expect(svgs).toHaveLength(1);
    expect(getByText("Customer Engagement")).toBeInTheDocument();
  });

  test("renders leading slot before label", () => {
    const { getByText, getByRole } = render(
      <ListSelectRow
        label="Acme AI"
        onClick={() => {}}
        leading={<span data-testid="logo">logo</span>}
      />
    );
    expect(getByText("logo")).toBeInTheDocument();
    expect(getByRole("button", { name: /Acme AI/ })).toBeInTheDocument();
  });

  test("leading + label + chevron — axe passes", async () => {
    const { container } = render(
      <ListSelectRow
        label="Acme AI"
        onClick={() => {}}
        leading={<LogoTile name="Acme AI" />}
      />
    );
    await expectNoAxeViolations(container);
  });

  test("disabled state", () => {
    const { getByRole } = render(
      <ListSelectRow label="Locked" onClick={() => {}} disabled />
    );
    expect(getByRole("button", { name: /Locked/ })).toBeDisabled();
  });

  test("calls onClick when clicked", () => {
    const onClick = jest.fn();
    const { getByRole } = render(
      <ListSelectRow label="Customer Engagement" onClick={onClick} />
    );
    getByRole("button", { name: /Customer Engagement/ }).click();
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  test("passes axe", async () => {
    const { container } = render(
      <ListSelectRow label="Customer Engagement" onClick={() => {}} />
    );
    await expectNoAxeViolations(container);
  });

  // branch mode
  test("branch mode: calls onToggle (not onClick) when clicked", () => {
    const onClick = jest.fn();
    const onToggle = jest.fn();
    const { getByRole } = render(
      <ListSelectRow label="Category" onClick={onClick} onToggle={onToggle} expanded={false} />
    );
    getByRole("button").click();
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });

  test("branch mode: aria-expanded reflects expanded prop", () => {
    const { getByRole, rerender } = render(
      <ListSelectRow label="Category" onClick={() => {}} onToggle={() => {}} expanded={false} />
    );
    expect(getByRole("button")).toHaveAttribute("aria-expanded", "false");
    rerender(
      <ListSelectRow label="Category" onClick={() => {}} onToggle={() => {}} expanded={true} />
    );
    expect(getByRole("button")).toHaveAttribute("aria-expanded", "true");
  });

  test("branch mode: children visible when expanded=true", () => {
    const { getByText } = render(
      <ListSelectRow label="Category" onClick={() => {}} onToggle={() => {}} expanded={true}>
        <span>Child item</span>
      </ListSelectRow>
    );
    expect(getByText("Child item")).toBeInTheDocument();
  });

  test("branch mode: children hidden when expanded=false", () => {
    const { queryByText } = render(
      <ListSelectRow label="Category" onClick={() => {}} onToggle={() => {}} expanded={false}>
        <span>Child item</span>
      </ListSelectRow>
    );
    expect(queryByText("Child item")).toBeNull();
  });

  test("branch mode: expanded passes axe", async () => {
    const { container } = render(
      <ListSelectRow label="Category" onClick={() => {}} onToggle={() => {}} expanded={true}>
        <ListSelectRow label="Sub-item" onClick={() => {}} />
      </ListSelectRow>
    );
    await expectNoAxeViolations(container);
  });
});

// ── LogoTile ──────────────────────────────────────────────────────────────────

describe("LogoTile", () => {
  test("renders img when src is present", () => {
    const { getByRole } = render(<LogoTile src="/logos/acme.svg" name="Acme AI" />);
    const img = getByRole("img", { name: "Acme AI" });
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "/logos/acme.svg");
  });

  test("renders monogram when src is null", () => {
    const { getByText, queryByRole } = render(<LogoTile src={null} name="Acme AI" />);
    expect(queryByRole("img")).toBeNull();
    expect(getByText("AA")).toBeInTheDocument();
  });

  test("renders monogram when src is undefined", () => {
    const { getByText } = render(<LogoTile name="Single" />);
    expect(getByText("S")).toBeInTheDocument();
  });

  test("monogram caps at 2 initials", () => {
    const { getByText } = render(<LogoTile name="Alpha Beta Gamma" />);
    expect(getByText("AB")).toBeInTheDocument();
  });

  test("has aria-label from name", () => {
    const { getByLabelText } = render(<LogoTile name="Acme AI" />);
    expect(getByLabelText("Acme AI")).toBeInTheDocument();
  });

  test("logo-present path passes axe", async () => {
    const { container } = render(<LogoTile src="/logos/acme.svg" name="Acme AI" />);
    await expectNoAxeViolations(container);
  });

  test("monogram path passes axe", async () => {
    const { container } = render(<LogoTile name="Acme AI" />);
    await expectNoAxeViolations(container);
  });
});

// ── DataTable ─────────────────────────────────────────────────────────────────

describe("DataTable", () => {
  test("composes existing TableBody — no duplicate tbody", () => {
    const { container } = render(
      <DataTable>
        <DataTableHeader>
          <TableHeaderCell>Name</TableHeaderCell>
        </DataTableHeader>
        <DataTableBody>
          <TableRow>
            <TableCell>System A</TableCell>
          </TableRow>
        </DataTableBody>
      </DataTable>
    );
    const tbodies = container.querySelectorAll("tbody");
    expect(tbodies).toHaveLength(1);
  });

  test("renders EmptyState when DataTableBody has no rows and emptyMessage given", () => {
    const { getByText } = render(
      <DataTable>
        <DataTableBody emptyMessage="No systems yet.">{null}</DataTableBody>
      </DataTable>
    );
    expect(getByText("No systems yet.")).toBeInTheDocument();
  });

  test("renders rows when provided", () => {
    const { getByText } = render(
      <DataTable>
        <DataTableBody>
          <TableRow>
            <TableCell>System A</TableCell>
          </TableRow>
        </DataTableBody>
      </DataTable>
    );
    expect(getByText("System A")).toBeInTheDocument();
  });

  test("wrapped in a border div", () => {
    const { container } = render(
      <DataTable>
        <DataTableBody>{null}</DataTableBody>
      </DataTable>
    );
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.tagName).toBe("DIV");
    expect(wrapper.className).toContain("rounded-lg");
  });

  test("passes axe with rows", async () => {
    const { container } = render(
      <DataTable>
        <DataTableHeader>
          <TableHeaderCell>Name</TableHeaderCell>
        </DataTableHeader>
        <DataTableBody>
          <TableRow>
            <TableCell>System A</TableCell>
          </TableRow>
        </DataTableBody>
      </DataTable>
    );
    await expectNoAxeViolations(container);
  });
});
