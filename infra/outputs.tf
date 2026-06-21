# After `terraform apply`, these print the values your backend needs.
#
# We OUTPUT them rather than writing your .env for you: Terraform owns the
# INFRASTRUCTURE; you stay in control of your config/secrets files. Copy into
# .env as:
#   COGNITO_OPERATOR_USER_POOL_ID=<operator_user_pool_id>
#   COGNITO_OPERATOR_APP_CLIENT_ID=<operator_app_client_id>
#   COGNITO_USER_POOL_ID=<tenant_user_pool_id>
#   COGNITO_APP_CLIENT_ID=<tenant_app_client_id>

output "operator_user_pool_id" {
  description = "Operator pool id -> COGNITO_OPERATOR_USER_POOL_ID"
  value       = aws_cognito_user_pool.operators.id
}

output "operator_app_client_id" {
  description = "Operator app client id -> COGNITO_OPERATOR_APP_CLIENT_ID"
  value       = aws_cognito_user_pool_client.operator_console.id
}

output "operator_pool_issuer" {
  description = "Issuer URL the token verifier checks against the `iss` claim."
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.operators.id}"
}

output "tenant_user_pool_id" {
  description = "Tenant pool id -> COGNITO_USER_POOL_ID"
  value       = aws_cognito_user_pool.tenants.id
}

output "tenant_app_client_id" {
  description = "Tenant app client id -> COGNITO_APP_CLIENT_ID"
  value       = aws_cognito_user_pool_client.irontrustai_web.id
}

output "tenant_pool_issuer" {
  description = "Issuer URL the tenant token verifier (verify_cognito_token) checks against the `iss` claim."
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.tenants.id}"
}

# Hosted-UI domains — the BFF's authorize/token endpoints are at
# https://<domain>.auth.<region>.amazoncognito.com/oauth2/{authorize,token}.
# Feed these into each app's COGNITO_*_DOMAIN env var (UI-F0-FOUNDATION, W3).

output "operator_hosted_ui_domain" {
  description = "Operator pool hosted-UI domain -> COGNITO_OPERATOR_DOMAIN"
  value       = aws_cognito_user_pool_domain.operators.domain
}

output "tenant_hosted_ui_domain" {
  description = "Tenant pool hosted-UI domain -> COGNITO_DOMAIN"
  value       = aws_cognito_user_pool_domain.tenants.domain
}
