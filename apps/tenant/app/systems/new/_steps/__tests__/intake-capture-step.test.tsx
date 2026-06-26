/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { IntakeCaptureStep } from "../intake-capture-step";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

/** GET reads (the six vocab lists) get an empty array; the POST create
 * gets the given response body. */
function mockFetchOk(createResponseBody: unknown) {
  global.fetch = jest.fn((_input: RequestInfo | URL, init?: RequestInit) => {
    const isCreate = init?.method === "POST";
    return Promise.resolve({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(isCreate ? createResponseBody : []),
    } as Response);
  }) as jest.Mock;
}

afterEach(() => {
  jest.restoreAllMocks();
});

function postInit(): RequestInit {
  const fetchMock = global.fetch as jest.Mock;
  const call = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "POST");
  if (!call) throw new Error("no POST call recorded");
  return call[1] as RequestInit;
}

describe("IntakeCaptureStep", () => {
  test("is_custom=true is unreachable alongside a catalogue product — the submitted body always nulls catalogue_product_id", async () => {
    mockFetchOk({ id: "sys-1", name: "x" });
    const onSubmit = jest.fn();

    render(
      <IntakeCaptureStep isCustom={true} catalogueProductId="should-never-be-sent" onSubmit={onSubmit} />,
      { wrapper }
    );

    // Vocab gate shows Skeleton until all vocab queries resolve
    await waitFor(() => screen.getByLabelText("System name"));
    fireEvent.change(screen.getByLabelText("System name"), { target: { value: "My System" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());

    const sentBody = JSON.parse(postInit().body as string);
    expect(sentBody.is_custom).toBe(true);
    expect(sentBody.catalogue_product_id).toBeNull();
  });

  test("a successful create calls onSubmit with the returned SystemDetail", async () => {
    const systemDetail = { id: "sys-1", name: "My System", is_custom: false };
    mockFetchOk(systemDetail);
    const onSubmit = jest.fn();

    render(<IntakeCaptureStep isCustom={false} catalogueProductId="p1" onSubmit={onSubmit} />, {
      wrapper,
    });

    await waitFor(() => screen.getByLabelText("System name"));
    fireEvent.change(screen.getByLabelText("System name"), { target: { value: "My System" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    // TanStack Query's onSuccess passes (data, variables, context, ...) —
    // assert on the first arg (the actual SystemDetail response) only.
    expect(onSubmit.mock.calls[0][0]).toEqual(systemDetail);
  });

  test("a catalogue-linked submit carries the catalogue_product_id forward, never catalogue_vendor_id", async () => {
    mockFetchOk({ id: "sys-1" });
    const onSubmit = jest.fn();

    render(<IntakeCaptureStep isCustom={false} catalogueProductId="p1" onSubmit={onSubmit} />, {
      wrapper,
    });

    await waitFor(() => screen.getByLabelText("System name"));
    fireEvent.change(screen.getByLabelText("System name"), { target: { value: "My System" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());

    const sentBody = JSON.parse(postInit().body as string);
    expect(sentBody.catalogue_product_id).toBe("p1");
    expect(sentBody.catalogue_vendor_id).toBeNull();
  });
});
