/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import { OperatorSidebar } from "../operator-sidebar";

// Mock next/link and next/navigation for the component under test.
jest.mock("next/link", () => {
  const Link = ({
    href,
    children,
    ...rest
  }: { href: string; children: React.ReactNode } & Record<string, unknown>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  );
  Link.displayName = "Link";
  return Link;
});

jest.mock("next/navigation", () => ({
  usePathname: () => "/provisioning",
}));

const ALL_PERMISSIONS = ["tenant:provision", "operator:create"];
const PROVISION_ONLY = ["tenant:provision"];
const NO_PERMISSIONS: string[] = [];

describe("OperatorSidebar — FE-13 RequirePermission gating", () => {
  test("with operator:create — RBAC Management link rendered", () => {
    render(<OperatorSidebar permissions={ALL_PERMISSIONS} />);
    expect(screen.getByText("RBAC Management")).toBeInTheDocument();
  });

  test("without operator:create — RBAC Management link absent", () => {
    render(<OperatorSidebar permissions={PROVISION_ONLY} />);
    expect(screen.queryByText("RBAC Management")).not.toBeInTheDocument();
  });

  test("with tenant:provision — Provisioning link rendered", () => {
    render(<OperatorSidebar permissions={PROVISION_ONLY} />);
    expect(screen.getByText("Provisioning")).toBeInTheDocument();
  });

  test("without tenant:provision — Provisioning link absent", () => {
    render(<OperatorSidebar permissions={NO_PERMISSIONS} />);
    expect(screen.queryByText("Provisioning")).not.toBeInTheDocument();
  });

  test("unbuilt items always render as disabled placeholders", () => {
    render(<OperatorSidebar permissions={NO_PERMISSIONS} />);
    expect(screen.getByText("Catalogue Curation")).toBeInTheDocument();
    expect(screen.getByText("Curation Inbox")).toBeInTheDocument();
    // Rendered as <span aria-disabled="true">, not a link
    expect(screen.queryByRole("link", { name: "Catalogue Curation" })).not.toBeInTheDocument();
  });

  test("active link carries aria-current=page (pathname=/provisioning)", () => {
    render(<OperatorSidebar permissions={ALL_PERMISSIONS} />);
    const link = screen.getByRole("link", { name: "Provisioning" });
    expect(link).toHaveAttribute("aria-current", "page");
  });
});
