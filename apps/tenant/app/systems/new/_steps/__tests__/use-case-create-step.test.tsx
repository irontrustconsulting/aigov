/**
 * @jest-environment jsdom
 */
import { useState } from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { UseCaseCreateStep, type UseCaseCreateStepProps } from "../use-case-create-step";

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
      confirmedIntakeFields={[]}
      confirmedFactKeys={[]}
      amendedFactKeys={[]}
      intakePrefillBases={null}
      onConfirmField={jest.fn()}
      onFieldChange={jest.fn()}
      onReviewFacts={jest.fn()}
      onCreated={onCreated}
    />,
    { wrapper },
  );

  // Wait for vocab queries to settle (returns [], so fields render empty but enabled)
  await waitFor(() => expect(screen.getByLabelText(/what are you using this for/i)).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/what are you using this for/i), { target: { value: "Support chatbot" } });
  fireEvent.click(screen.getByRole("button", { name: /register/i }));

  await waitFor(() => expect(onCreated).toHaveBeenCalled());
  const [result] = onCreated.mock.calls[0] as [typeof REGISTRATION_RESPONSE, unknown];
  expect(result.use_case.id).toBe("uc-1");
  expect(result.classification.requires_context).toBe(true);
});

const DATA_CATEGORIES = [
  { id: "dc-1", code: "health", label: "Health Data", is_special_category: true },
  { id: "dc-2", code: "identifiers", label: "Identifiers", is_special_category: false },
];
const AFFECTED_PARTIES = [
  { id: "ap-1", code: "children", label: "Children", is_vulnerable_group: true },
  { id: "ap-2", code: "employees", label: "Employees", is_vulnerable_group: false },
];

function mockVocabFetch() {
  global.fetch = jest.fn().mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
    if ((init?.method ?? "GET").toUpperCase() === "POST") {
      return Promise.resolve({
        ok: true, status: 201,
        text: async () => JSON.stringify(REGISTRATION_RESPONSE),
      } as Response);
    }
    const path = String(url);
    if (path.includes("/data-categories")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(DATA_CATEGORIES) } as Response);
    }
    if (path.includes("/affected-parties")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(AFFECTED_PARTIES) } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response);
  }) as jest.Mock;
}

test("title renders as the TextInput primitive with a placeholder", async () => {
  mockVocabFetch();
  render(
    <UseCaseCreateStep
      name="Test" isCustom={true} catalogueProductId={null} operatorRoleId={null}
      hostingModelId={null} lifecycleStage={null} purpose={null} draftId={null}
      confirmedIntakeFields={[]} confirmedFactKeys={[]} amendedFactKeys={[]}
      intakePrefillBases={null} onConfirmField={jest.fn()} onFieldChange={jest.fn()} onReviewFacts={jest.fn()}
      onCreated={jest.fn()}
    />,
    { wrapper },
  );

  const titleInput = await screen.findByLabelText(/what are you using this for/i);
  expect(titleInput).toHaveAttribute("placeholder", "e.g. Screening inbound support tickets");
  expect(titleInput).toHaveValue("");
});

test("renders both SectionGroup headings and both grouped clusters with duty/other subgroups", async () => {
  mockVocabFetch();
  render(
    <UseCaseCreateStep
      name="Test" isCustom={true} catalogueProductId={null} operatorRoleId={null}
      hostingModelId={null} lifecycleStage={null} purpose={null} draftId={null}
      confirmedIntakeFields={[]} confirmedFactKeys={[]} amendedFactKeys={[]}
      intakePrefillBases={null} onConfirmField={jest.fn()} onFieldChange={jest.fn()} onReviewFacts={jest.fn()}
      onCreated={jest.fn()}
    />,
    { wrapper },
  );

  await screen.findByLabelText(/what are you using this for/i);

  expect(screen.getByText("Use & oversight")).toBeInTheDocument();
  expect(screen.getByText("Data & affected parties")).toBeInTheDocument();

  // data-categories: duty (special-category) + other subgroup
  expect(screen.getByText("GDPR Art. 9, heightened duty")).toBeInTheDocument();
  expect(screen.getByText("Health Data")).toBeInTheDocument();
  expect(screen.getByText("Identifiers")).toBeInTheDocument();

  // affected-parties: duty (vulnerable-group) + other subgroup
  expect(screen.getByText("EU AI Act Art. 27, heightened duty")).toBeInTheDocument();
  expect(screen.getByText("Children")).toBeInTheDocument();
  expect(screen.getByText("Employees")).toBeInTheDocument();

  // all fields empty on first render — no chip pre-checked
  const checkboxes = screen.getAllByRole("checkbox");
  checkboxes.forEach((cb) => expect(cb).not.toBeChecked());
});

// ---------------------------------------------------------------------------
// FIX-RESUME-REGATE: pre-commit disposition gate integration (WI-4)
// ---------------------------------------------------------------------------

const OPERATOR_ROLES = [{ id: "role-deployer", code: "deployer", label: "Deployer" }];
const PREFILL_FACTS = [
  { key: "hosting_region", value: { list: ["EEA"] }, source_url: null, source_label: "Vendor DPA", last_checked_at: null, provenance: "catalogue_curated" },
  { key: "dpa_available", value: { answer: true }, source_url: null, source_label: "Vendor DPA", last_checked_at: null, provenance: "catalogue_curated" },
];

function mockResumeFetch() {
  global.fetch = jest.fn().mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const path = String(url);
    if (method === "POST" && path.includes("/registrations")) {
      const body = JSON.parse(String(init?.body ?? "{}"));
      return Promise.resolve({
        ok: true,
        status: 201,
        text: async () => JSON.stringify({ ...REGISTRATION_RESPONSE, __confirmed_fields: body.confirmed_fields }),
      } as Response);
    }
    if (path.includes("/data-categories")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(DATA_CATEGORIES) } as Response);
    }
    if (path.includes("/affected-parties")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(AFFECTED_PARTIES) } as Response);
    }
    if (path.includes("/operator-roles")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(OPERATOR_ROLES) } as Response);
    }
    if (path.includes("/prefill")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ catalogue_product_id: "prod-1", facts: PREFILL_FACTS, field_prefills: null }),
      } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response);
  }) as jest.Mock;
}

function ControlledResumeStep(props: Partial<UseCaseCreateStepProps> & { onCreated: UseCaseCreateStepProps["onCreated"] }) {
  const [confirmedIntakeFields, setConfirmedIntakeFields] = useState<string[]>([]);
  return (
    <UseCaseCreateStep
      name="Test"
      isCustom={false}
      catalogueProductId="prod-1"
      operatorRoleId="role-deployer"
      hostingModelId={null}
      lifecycleStage="production"
      purpose={null}
      draftId={null}
      confirmedFactKeys={[]}
      amendedFactKeys={[]}
      intakePrefillBases={{ operatorRoleId: "derived", lifecycleStage: "derived" }}
      onConfirmField={(field) => setConfirmedIntakeFields((prev) => [...prev, field])}
      onFieldChange={jest.fn()}
      onReviewFacts={jest.fn()}
      confirmedIntakeFields={confirmedIntakeFields}
      {...props}
    />
  );
}

test("resume with unconfirmed derived defaults: gate renders, Register is disabled, confirming enables it and registers without a 422", async () => {
  mockResumeFetch();
  const onCreated = jest.fn();

  render(<ControlledResumeStep onCreated={onCreated} />, { wrapper });

  await screen.findByText("Operator role");
  expect(screen.getByText("Lifecycle stage")).toBeInTheDocument();
  expect(screen.getAllByText("Derived, confirm or update")).toHaveLength(2);

  const registerButton = screen.getByRole("button", { name: /register/i });
  expect(registerButton).toBeDisabled();
  expect(screen.getByText(/confirm operator role and lifecycle stage to continue/i)).toBeInTheDocument();

  fireEvent.click(screen.getAllByRole("button", { name: "Confirm" })[0]!);
  fireEvent.click(screen.getAllByRole("button", { name: "Confirm" })[0]!);

  await waitFor(() => expect(registerButton).not.toBeDisabled());
  expect(screen.queryByText("Before you register")).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText(/what are you using this for/i), { target: { value: "Support chatbot" } });
  fireEvent.click(registerButton);
  await waitFor(() => expect(onCreated).toHaveBeenCalled());
  const postCall = (global.fetch as jest.Mock).mock.calls.find(
    ([, init]) => (init?.method ?? "").toUpperCase() === "POST"
  );
  const body = JSON.parse(String(postCall![1].body));
  expect(body.confirmed_fields).toEqual(expect.arrayContaining(["operator_role_id", "lifecycle_stage"]));
});

test("normal (non-resumed) flow: derived fields already confirmed, gate never renders", async () => {
  mockResumeFetch();
  render(
    <ControlledResumeStep
      onCreated={jest.fn()}
      confirmedIntakeFields={["operatorRoleId", "lifecycleStage"]}
    />,
    { wrapper }
  );

  await screen.findByLabelText(/what are you using this for/i);
  expect(screen.queryByText("Before you register")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /register/i })).not.toBeDisabled();
});

test("resume with unreviewed catalogue facts (alongside an unconfirmed derived field): recap renders the count, confirmed_fields carries no fact: entries", async () => {
  mockResumeFetch();
  const onCreated = jest.fn();
  render(<ControlledResumeStep onCreated={onCreated} />, { wrapper });

  await screen.findByText(/2 catalogue facts have not been reviewed this session/);

  // clear the hard gate (derived confirms) so Register is reachable
  fireEvent.click(screen.getAllByRole("button", { name: "Confirm" })[0]!);
  fireEvent.click(screen.getAllByRole("button", { name: "Confirm" })[0]!);
  const registerButton = await screen.findByRole("button", { name: /register/i });
  await waitFor(() => expect(registerButton).not.toBeDisabled());

  fireEvent.change(screen.getByLabelText(/what are you using this for/i), { target: { value: "Support chatbot" } });
  fireEvent.click(registerButton);
  await waitFor(() => expect(onCreated).toHaveBeenCalled());
  const postCall = (global.fetch as jest.Mock).mock.calls.find(
    ([, init]) => (init?.method ?? "").toUpperCase() === "POST"
  );
  const body = JSON.parse(String(postCall![1].body));
  expect(body.confirmed_fields.some((f: string) => f.startsWith("fact:"))).toBe(false);
});

test("Review-facts link fires onReviewFacts", async () => {
  mockResumeFetch();
  const onReviewFacts = jest.fn();
  render(<ControlledResumeStep onCreated={jest.fn()} onReviewFacts={onReviewFacts} />, { wrapper });

  await screen.findByText(/catalogue facts have not been reviewed this session/);
  fireEvent.click(screen.getByText("Review facts ›"));
  expect(onReviewFacts).toHaveBeenCalled();
});
