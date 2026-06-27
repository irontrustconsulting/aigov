/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { UseCaseCreateStep } from "../use-case-create-step";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockFetchOk(body: unknown) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    text: async () => JSON.stringify(body),
  } as Response) as jest.Mock;
}

afterEach(() => jest.restoreAllMocks());

test("a successful create hands the use case id and classification up via onCreated", async () => {
  mockFetchOk({
    use_case: { id: "uc-1", tenant_id: "t1", system_id: "sys-1", title: "x", purpose: null, state: "intake", eu_tier: "unclassified" },
    classification: {
      id: "c1",
      use_case_id: "uc-1",
      tier: "requires_context",
      rationale: "no product mapping",
      version: 1,
      is_current: true,
      overridden: false,
      proposed_tier: null,
      basis_subcategory_code: null,
      basis_legal_ref: null,
      requires_context: true,
    },
  });
  const onCreated = jest.fn();

  render(<UseCaseCreateStep systemId="sys-1" usageContextId={null} humanOversightTypeId={null} dataCategoryIds={[]} affectedPartyIds={[]} onCreated={onCreated} />, { wrapper });

  fireEvent.change(screen.getByLabelText(/what are you using this for/i), { target: { value: "Support chatbot" } });
  fireEvent.click(screen.getByRole("button", { name: /continue/i }));

  await waitFor(() => expect(onCreated).toHaveBeenCalled());
  expect(onCreated.mock.calls[0][0]).toBe("uc-1");
  expect(onCreated.mock.calls[0][1].requires_context).toBe(true);
});
