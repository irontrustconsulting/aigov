/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import { TerminalProhibited } from "../terminal-prohibited";

test("TerminalProhibited renders the hard-stop with no advance control", () => {
  render(<TerminalProhibited />);
  expect(screen.getByRole("alert")).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
