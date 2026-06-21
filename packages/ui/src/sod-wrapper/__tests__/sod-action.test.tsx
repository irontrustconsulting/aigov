import { render, screen } from "@testing-library/react";
import { SodAction } from "../sod-action";
import { Button } from "../../primitives/button";
import { expectNoAxeViolations } from "../../../test-utils/axe";

describe("SodAction", () => {
  test("barred=true renders nothing — the child is absent from the DOM, not disabled", () => {
    render(
      <SodAction barred={true}>
        <Button>Approve</Button>
      </SodAction>
    );
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  test("barred=false, no blockedReason renders the child enabled", () => {
    render(
      <SodAction barred={false}>
        <Button>Approve</Button>
      </SodAction>
    );
    const button = screen.getByRole("button", { name: "Approve" });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  test("barred=false with blockedReason renders the child disabled with the reason accessible", () => {
    render(
      <SodAction barred={false} blockedReason="Use case is not in a workable state">
        <Button>Approve</Button>
      </SodAction>
    );
    const button = screen.getByRole("button", { name: "Approve" });
    expect(button).toBeDisabled();
    expect(screen.getByText("Use case is not in a workable state")).toBeInTheDocument();
  });

  test("passes axe with no violations in each render state", async () => {
    const { container, rerender } = render(
      <SodAction barred={false}>
        <Button>Approve</Button>
      </SodAction>
    );
    await expectNoAxeViolations(container);

    rerender(
      <SodAction barred={false} blockedReason="Stale lock">
        <Button>Approve</Button>
      </SodAction>
    );
    await expectNoAxeViolations(container);
  });
});
