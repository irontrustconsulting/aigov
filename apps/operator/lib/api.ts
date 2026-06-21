import { createApiClient } from "@irontrust/api-client";

// Relative, same-origin — calls only this app's own BFF proxy, never the
// API directly (FE-9).
export const api = createApiClient({ baseUrl: "/api/proxy" });
