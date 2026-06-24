import { render, screen } from "@testing-library/react";
import { StaleLockBanner } from "../stale-lock-banner";
import { BadFromStateBanner } from "../bad-from-state-banner";
import { expectNoAxeViolations } from "../../../test-utils/axe";

describe("StaleLockBanner (412) vs BadFromStateBanner (409) — distinct surfaces", () => {
  test("StaleLockBanner renders a Reload button", () => {
    render(<StaleLockBanner onReload={jest.fn()} />);
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
  });

  test("BadFromStateBanner renders no retry affordance", () => {
    render(<BadFromStateBanner />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  test("StaleLockBanner has data-concurrency=412", () => {
    const { container } = render(<StaleLockBanner onReload={jest.fn()} />);
    expect((container.firstChild as HTMLElement).dataset.concurrency).toBe("412");
  });

  test("BadFromStateBanner has data-concurrency=409", () => {
    const { container } = render(<BadFromStateBanner />);
    expect((container.firstChild as HTMLElement).dataset.concurrency).toBe("409");
  });

  test("the two banners are identifiably distinct surfaces", () => {
    const { container: c1 } = render(<StaleLockBanner onReload={jest.fn()} />);
    const { container: c2 } = render(<BadFromStateBanner />);
    const staleCode = (c1.firstChild as HTMLElement).dataset.concurrency;
    const badCode = (c2.firstChild as HTMLElement).dataset.concurrency;
    expect(staleCode).not.toBe(badCode);
  });
});

describe("Concurrency surfaces — axe", () => {
  test("StaleLockBanner passes axe", async () => {
    const { container } = render(<StaleLockBanner onReload={jest.fn()} />);
    await expectNoAxeViolations(container);
  });

  test("BadFromStateBanner passes axe", async () => {
    const { container } = render(<BadFromStateBanner />);
    await expectNoAxeViolations(container);
  });
});
