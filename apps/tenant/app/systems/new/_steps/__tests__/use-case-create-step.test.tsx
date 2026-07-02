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

afterEach(() => jest.restoreAllMocks());

const REGISTRATION_RESPONSE = {
  system: {
    id: "sys-1", name: "Test", is_custom: true, catalogue_product: null,
    catalogue_vendor: null, owner_user_id: null, operator_role: null,
    hosting_model: null, lifecycle_stage: null, purpose: null,
    use_case_count: 0, use_case_lifecycle_states: [],
    created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  },
  use_case: {
    id: "uc-1", tenant_id: "t1", system_id: "sys-1", title: "x",
    state: "intake", eu_tier: "unclassified", usage_context: null,
    human_oversight_type: null, data_categories: [], affected_parties: [],
  },
  classification: {
    id: "c1", use_case_id: "uc-1", tier: "requires_context",
    rationale: "no product mapping", version: 1, is_current: true,
    overridden: false, proposed_tier: null, basis_subcategory_code: null,
    basis_legal_ref: null, requires_context: true, status: "pending_review",
  },
};

test("a successful register hands the full RegistrationRead up via onCreated", async () => {
  // GET vocab/category requests return []; POST /registrations returns REGISTRATION_RESPONSE
  global.fetch = jest.fn().mockImplementation((_url: RequestInfo | URL, init?: RequestInit) => {
    if ((init?.method ?? "GET").toUpperCase() === "POST") {
      return Promise.resolve({
        ok: true, status: 201,
        text: async () => JSON.stringify(REGISTRATION_RESPONSE),
      } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response);
  }) as jest.Mock;

  const onCreated = jest.fn();

  render(
    <UseCaseCreateStep
      name="Test"
      isCustom={true}
      catalogueProductId={null}
      operatorRoleId={null}
      hostingModelId={null}
      lifecycleStage={null}
      purpose={null}
      draftId={null}
      onCreated={onCreated}
    />,
    { wrapper },
  );

  // Wait for vocab queries to settle (returns [], so fields render empty but enabled)
  await waitFor(() => expect(screen.getByLabelText(/what are you using this for/i)).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/what are you using this for/i), { target: { value: "Support chatbot" } });
  fireEvent.click(screen.getByRole("button", { name: /continue/i }));

  await waitFor(() => expect(onCreated).toHaveBeenCalled());
  const [result] = onCreated.mock.calls[0] as [typeof REGISTRATION_RESPONSE, unknown];
  expect(result.use_case.id).toBe("uc-1");
  expect(result.classification.requires_context).toBe(true);
});
