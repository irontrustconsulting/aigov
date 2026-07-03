/**
 * @jest-environment jsdom
 *
 * IntakeCaptureStep (DM-S4a): fully wizard-state-controlled; values come from
 * props, changes dispatch onFieldChange, submit calls onSubmit() with no args.
 * Seeded fields show FE-30 basis captions; user edits invoke onFieldChange so
 * the reducer can clear the basis to user-set.
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { IntakeCaptureStep } from "../intake-capture-step";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const DEFAULT_PROPS = {
  isCustom: false,
  name: "",
  operatorRoleId: null,
  hostingModelId: null,
  lifecycleStage: null,
  purpose: null,
  prefillBases: null,
  confirmedIntakeFields: [] as string[],
  onFieldChange: jest.fn(),
  onConfirmField: jest.fn(),
  onSubmit: jest.fn(),
} as const;

function mockVocabEmpty() {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response)
  ) as jest.Mock;
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("IntakeCaptureStep", () => {
  test("Continue button calls onSubmit with no args — values already in wizard state", async () => {
    mockVocabEmpty();
    const onSubmit = jest.fn();
    render(<IntakeCaptureStep {...DEFAULT_PROPS} name="My System" onSubmit={onSubmit} />, { wrapper });

    await waitFor(() => screen.getByLabelText("System name"));
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith();

    // No mutation — fetch only for vocab GETs
    const fetchMock = global.fetch as jest.Mock;
    const postCalls = fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    expect(postCalls).toHaveLength(0);
  });

  test("name change dispatches onFieldChange with field='name'", async () => {
    mockVocabEmpty();
    const onFieldChange = jest.fn();
    render(<IntakeCaptureStep {...DEFAULT_PROPS} onFieldChange={onFieldChange} />, { wrapper });

    await waitFor(() => screen.getByLabelText("System name"));
    fireEvent.change(screen.getByLabelText("System name"), { target: { value: "Custom AI" } });

    expect(onFieldChange).toHaveBeenCalledWith("name", "Custom AI");
  });

  test("basis caption renders for seeded catalogue field and absent for user-set", async () => {
    mockVocabEmpty();
    render(
      <IntakeCaptureStep
        {...DEFAULT_PROPS}
        operatorRoleId="role-1"
        hostingModelId="hm-1"
        lifecycleStage="production"
        prefillBases={{
          operatorRoleId: "catalogue",
          hostingModelId: "user-set",
          lifecycleStage: "derived",
        }}
      />,
      { wrapper }
    );

    await waitFor(() => screen.getByLabelText("System name"));
    // catalogue basis shows caption
    expect(screen.getByText("Catalogue curated — confirm or update")).toBeInTheDocument();
    // derived basis shows caption
    expect(screen.getByText("Derived — confirm or update")).toBeInTheDocument();
    // user-set shows no caption (only 2 captions total: catalogue + derived)
    expect(screen.getAllByText(/— confirm or update/)).toHaveLength(2);
  });

  test("no basis captions when prefillBases is null (custom / unseeded path)", async () => {
    mockVocabEmpty();
    render(<IntakeCaptureStep {...DEFAULT_PROPS} />, { wrapper });

    await waitFor(() => screen.getByLabelText("System name"));
    expect(screen.queryByText(/confirm or update/i)).toBeNull();
  });
});
