import { createApiClient } from "../client";
import { StaleLockError, BadFromStateError } from "../errors";
import { ForbiddenFieldError } from "../guards";

beforeEach(() => {
  // jsdom's test environment does not define a global fetch — assign one so
  // it can be mocked per-test rather than spying on a property that doesn't exist.
  global.fetch = jest.fn();
});

afterEach(() => {
  jest.restoreAllMocks();
});

function mockFetchOnce(status: number, body: unknown) {
  const fetchMock = global.fetch as jest.Mock;
  fetchMock.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response);
  return fetchMock;
}

describe("createApiClient", () => {
  test("a mutation with lockVersion sends If-Match", async () => {
    const fetchSpy = mockFetchOnce(200, { ok: true });
    const client = createApiClient({ baseUrl: "/api/proxy" });

    await client.patch("/v1/use-cases/123", { name: "x" }, { lockVersion: "7" });

    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["If-Match"]).toBe("7");
  });

  test("412 produces a StaleLockError, 409 produces a BadFromStateError — distinct types", async () => {
    const client = createApiClient({ baseUrl: "/api/proxy" });

    mockFetchOnce(412, { detail: "stale" });
    await expect(client.patch("/v1/x", { a: 1 })).rejects.toBeInstanceOf(StaleLockError);

    mockFetchOnce(409, { detail: "bad state" });
    await expect(client.patch("/v1/x", { a: 1 })).rejects.toBeInstanceOf(BadFromStateError);
  });

  test("a body containing tenant_id throws before fetch is called", async () => {
    const client = createApiClient({ baseUrl: "/api/proxy" });

    await expect(
      client.post("/v1/systems", { name: "x", tenant_id: "evil" } as never)
    ).rejects.toBeInstanceOf(ForbiddenFieldError);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test("a body containing provenance throws before fetch is called", async () => {
    const client = createApiClient({ baseUrl: "/api/proxy" });

    await expect(
      client.patch("/v1/items/1", { provenance: "AI_SUGGESTED" } as never)
    ).rejects.toBeInstanceOf(ForbiddenFieldError);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
