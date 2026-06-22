/**
 * Dedicated BFF upload handler for evidence files (FE-12, DF5-2, WI-C).
 *
 * The generic [...path] proxy uses `await request.text()` which UTF-8-decodes
 * and buffers the entire body, corrupting binary file bytes and the multipart
 * boundary (V-8). This handler forwards raw bytes via arrayBuffer() instead,
 * preserving the multipart/form-data Content-Type and boundary parameter.
 *
 * Upload flow: browser → this handler → POST /v1/evidence (API). Never expose
 * the bearer token to the browser (INV-50).
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getSession } from "@/lib/auth/get-session";
import { isSameOriginRequest } from "@/lib/auth/csrf";

/** BFF body-size ceiling (V-9: API/config cap unknown; BFF imposes a hard stop). */
const MAX_BYTES = 50 * 1024 * 1024; // 50 MB

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!isSameOriginRequest(request)) {
    return NextResponse.json({ error: "Cross-origin request rejected" }, { status: 403 });
  }

  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.includes("multipart/form-data")) {
    return NextResponse.json({ error: "Expected multipart/form-data" }, { status: 400 });
  }

  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (contentLength > MAX_BYTES) {
    return NextResponse.json(
      { error: `File exceeds the ${MAX_BYTES / 1024 / 1024} MB limit` },
      { status: 413 }
    );
  }

  const apiBaseUrl = process.env.API_BASE_URL;
  if (!apiBaseUrl) throw new Error("Missing required env var API_BASE_URL");

  // Forward raw bytes — arrayBuffer() preserves binary content and the multipart
  // boundary. NEVER request.text(): UTF-8 decode corrupts binary files (FE-12, V-8).
  const body = await request.arrayBuffer();

  const apiResponse = await fetch(`${apiBaseUrl}/v1/evidence`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${session.idToken}`,
      "Content-Type": contentType, // preserves the boundary= parameter
    },
    body,
  });

  const responseBody = await apiResponse.text();
  return new NextResponse(responseBody, {
    status: apiResponse.status,
    headers: {
      "Content-Type": apiResponse.headers.get("content-type") ?? "application/json",
    },
  });
}
