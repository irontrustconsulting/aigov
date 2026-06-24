/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import { RequirePermission } from "../require-permission";

describe("RequirePermission (FE-13, INV-8)", () => {
  test("renders children when permission is present", () => {
    render(
      <RequirePermission permission="operator:provision" permissions={["operator:provision", "operator:view"]}>
        <button>Provision</button>
      </RequirePermission>
    );
    expect(screen.getByRole("button", { name: "Provision" })).toBeInTheDocument();
  });

  test("renders nothing when permission is absent — child NOT in DOM", () => {
    render(
      <RequirePermission permission="operator:provision" permissions={["operator:view"]}>
        <button>Provision</button>
      </RequirePermission>
    );
    expect(screen.queryByRole("button", { name: "Provision" })).not.toBeInTheDocument();
  });

  test("renders nothing with empty permissions array", () => {
    render(
      <RequirePermission permission="operator:provision" permissions={[]}>
        <button>Provision</button>
      </RequirePermission>
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  test("grants one permission does not grant another", () => {
    const { rerender } = render(
      <RequirePermission permission="operator:provision" permissions={["operator:manage"]}>
        <button>Provision</button>
      </RequirePermission>
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();

    rerender(
      <RequirePermission permission="operator:provision" permissions={["operator:provision"]}>
        <button>Provision</button>
      </RequirePermission>
    );
    expect(screen.getByRole("button")).toBeInTheDocument();
  });
});
