import { errorFromResponse } from "./errors";
import { assertNoForbiddenFields } from "./guards";
import type { ApiClientOptions, MutationBody, RequestOptions } from "./types";

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export interface ApiClient {
  get<T>(path: string, options?: RequestOptions): Promise<T>;
  post<T, B = unknown>(path: string, body: MutationBody<B>, options?: RequestOptions): Promise<T>;
  put<T, B = unknown>(path: string, body: MutationBody<B>, options?: RequestOptions): Promise<T>;
  patch<T, B = unknown>(
    path: string,
    body: MutationBody<B>,
    options?: RequestOptions
  ): Promise<T>;
  delete<T>(path: string, options?: RequestOptions): Promise<T>;
}

/**
 * Typed fetch wrapper calling only the app's own BFF proxy (FE-9) — baseUrl
 * is a relative, same-origin path; never an absolute API origin URL.
 */
export function createApiClient({ baseUrl }: ApiClientOptions): ApiClient {
  async function request<T>(
    method: string,
    path: string,
    body: unknown | undefined,
    options: RequestOptions | undefined
  ): Promise<T> {
    if (body !== undefined) {
      assertNoForbiddenFields(body);
    }

    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (options?.lockVersion) headers["If-Match"] = options.lockVersion;

    const res = await fetch(`${baseUrl}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: options?.signal,
      credentials: "same-origin",
    });

    if (!res.ok) {
      const parsed = await parseBody(res);
      throw errorFromResponse(res.status, parsed);
    }

    if (res.status === 204) return undefined as T;
    return (await parseBody(res)) as T;
  }

  return {
    get: (path, options) => request("GET", path, undefined, options),
    post: (path, body, options) => request("POST", path, body, options),
    put: (path, body, options) => request("PUT", path, body, options),
    patch: (path, body, options) => request("PATCH", path, body, options),
    delete: (path, options) => request("DELETE", path, undefined, options),
  };
}
