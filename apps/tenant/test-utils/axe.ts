import { axe, toHaveNoViolations } from "jest-axe";

expect.extend(toHaveNoViolations);

export async function expectNoAxeViolations(container: Element): Promise<void> {
  const results = await axe(container);
  expect(results).toHaveNoViolations();
}
