import { render } from "@testing-library/react";
import { TableCell, TableHeaderCell, TableRow } from "../../primitives/table";
import { StatCard } from "../stat-card";
import { SectionHeader } from "../section-header";
import { ListSelectRow } from "../list-select-row";
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

  test("has exactly one ChevronRight icon (no per-row action label)", () => {
    const { container } = render(
      <ListSelectRow label="Customer Engagement" onClick={() => {}} />
    );
    const svgs = container.querySelectorAll("svg");
    expect(svgs).toHaveLength(1);
    // No text beyond the label (no per-row label like "Browse" or "Select")
    const button = container.querySelector("button")!;
    const spans = button.querySelectorAll("span");
    expect(spans).toHaveLength(1);
    expect(spans[0].textContent).toBe("Customer Engagement");
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
