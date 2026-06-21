/**
 * Operator-pool Cognito + app config, read once from env. Never shared with
 * apps/tenant (FE-1: auth/cookie/pool config is never shared between
 * planes) — apps/tenant has its own, near-identical copy of this file.
 */
function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required env var ${name}`);
  }
  return value;
}

export const authEnv = {
  get region() {
    return required("COGNITO_OPERATOR_REGION");
  },
  get userPoolId() {
    return required("COGNITO_OPERATOR_USER_POOL_ID");
  },
  get clientId() {
    return required("COGNITO_OPERATOR_APP_CLIENT_ID");
  },
  get domain() {
    return required("COGNITO_OPERATOR_DOMAIN");
  },
  get appOrigin() {
    return process.env.APP_ORIGIN ?? "http://localhost:3001";
  },
  get hostedUiBase() {
    return `https://${this.domain}.auth.${this.region}.amazoncognito.com`;
  },
  get callbackUrl() {
    return `${this.appOrigin}/api/auth/callback`;
  },
  get logoutRedirectUrl() {
    return `${this.appOrigin}/`;
  },
};
