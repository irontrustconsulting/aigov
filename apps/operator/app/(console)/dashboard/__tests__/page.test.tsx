/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "../page";

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>
  );
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("DashboardPage (W7a smoke surface, operator)", () => {
  test("renders the caller's identity from GET /platform/me", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          id: "op-1",
          email: "operator@irontrust.test",
          display_name: "Operator One",
          permissions: ["tenant:provision"],
        }),
    } as Response);

    renderWithClient();

    await waitFor(() =>
      expect(screen.getByText("operator@irontrust.test")).toBeInTheDocument()
    );
    expect(screen.getByText("tenant:provision")).toBeInTheDocument();
  });

  test("shows an error state when the call fails", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 403,
      text: async () => JSON.stringify({ detail: "Forbidden" }),
    } as Response);

    renderWithClient();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});
