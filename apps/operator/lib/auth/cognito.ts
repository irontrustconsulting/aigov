import { authEnv } from "./env";

interface TokenResponse {
  id_token: string;
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  token_type: string;
}

export function buildAuthorizeUrl(state: string, codeChallenge: string): string {
  const params = new URLSearchParams({
    response_type: "code",
    client_id: authEnv.clientId,
    redirect_uri: authEnv.callbackUrl,
    scope: "openid email profile",
    state,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
  });
  return `${authEnv.hostedUiBase}/oauth2/authorize?${params.toString()}`;
}

export function buildLogoutUrl(): string {
  const params = new URLSearchParams({
    client_id: authEnv.clientId,
    logout_uri: authEnv.logoutRedirectUrl,
  });
  return `${authEnv.hostedUiBase}/logout?${params.toString()}`;
}

async function postToken(body: URLSearchParams): Promise<TokenResponse> {
  const res = await fetch(`${authEnv.hostedUiBase}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    throw new Error(`Cognito token endpoint returned ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<TokenResponse>;
}

export async function exchangeCodeForTokens(
  code: string,
  codeVerifier: string
): Promise<TokenResponse> {
  return postToken(
    new URLSearchParams({
      grant_type: "authorization_code",
      client_id: authEnv.clientId,
      code,
      redirect_uri: authEnv.callbackUrl,
      code_verifier: codeVerifier,
    })
  );
}

export async function refreshTokens(refreshToken: string): Promise<TokenResponse> {
  return postToken(
    new URLSearchParams({
      grant_type: "refresh_token",
      client_id: authEnv.clientId,
      refresh_token: refreshToken,
    })
  );
}

/** Decode the ID token's `sub` claim without verifying signature — the BFF
 * trusts it because it came directly from Cognito's token endpoint over TLS,
 * not from an untrusted bearer; this is for session bookkeeping only, never
 * used as an authorization decision (the API re-verifies the token on every
 * proxied request via verify_cognito_token). */
export function decodeSub(idToken: string): string {
  const payload = idToken.split(".")[1];
  if (!payload) throw new Error("Malformed ID token");
  const json = JSON.parse(Buffer.from(payload, "base64url").toString("utf-8"));
  return json.sub;
}
