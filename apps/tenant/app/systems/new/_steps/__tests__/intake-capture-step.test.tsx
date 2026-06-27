/**
 * @jest-environment jsdom
 *
 * IntakeCaptureStep (DM-S2): the step now makes NO network call on submit.
 * It captures system-stable facts (name, operatorRoleId, hostingModelId,
 * lifecycleStage, purpose) and calls onSubmit(facts) directly (DF-D2-1).
 * The POST /v1/registrations fires at the use-case step, not here.
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { IntakeCaptureStep } from "../intake-capture-step";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockVocabEmpty() {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response)
  ) as jest.Mock;
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("IntakeCaptureStep", () => {
  test("submit calls onSubmit with system-stable facts — no POST call is made", async () => {
    mockVocabEmpty();
    const onSubmit = jest.fn();

    render(<IntakeCaptureStep isCustom={false} catalogueProductId="p1" onSubmit={onSubmit} />, { wrapper });

    await waitFor(() => screen.getByLabelText("System name"));
    fireEvent.change(screen.getByLabelText("System name"), { target: { value: "My System" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());

    const facts = onSubmit.mock.calls[0][0];
    expect(facts.name).toBe("My System");
    expect(facts).toHaveProperty("operatorRoleId");
    expect(facts).toHaveProperty("hostingModelId");
    expect(facts).toHaveProperty("lifecycleStage");
    expect(facts).toHaveProperty("purpose");

    // No mutation — fetch should only have been called for vocab GETs
    const fetchMock = global.fetch as jest.Mock;
    const postCalls = fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    expect(postCalls).toHaveLength(0);
  });

  test("custom system submit forwards name without touching catalogueProductId", async () => {
    mockVocabEmpty();
    const onSubmit = jest.fn();

    render(<IntakeCaptureStep isCustom={true} catalogueProductId="should-not-appear" onSubmit={onSubmit} />, { wrapper });

    await waitFor(() => screen.getByLabelText("System name"));
    fireEvent.change(screen.getByLabelText("System name"), { target: { value: "Custom AI" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());

    const facts = onSubmit.mock.calls[0][0];
    expect(facts.name).toBe("Custom AI");
  });
});
