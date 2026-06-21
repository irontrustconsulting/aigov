import { render, screen } from "@testing-library/react";
import { Button } from "../button";
import { expectNoAxeViolations } from "../../../test-utils/axe";

describe("Button", () => {
  test("renders its children and is disableable", () => {
    render(<Button disabled>Submit</Button>);
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });

  test("passes axe with no violations", async () => {
    const { container } = render(<Button>Submit</Button>);
    await expectNoAxeViolations(container);
  });
});
