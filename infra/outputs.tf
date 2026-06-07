# After `terraform apply`, these print the values your backend needs.
#
# We OUTPUT them rather than writing your .env for you: Terraform owns the
# INFRASTRUCTURE; you stay in control of your config/secrets files. Copy into
# .env as:
#   COGNITO_OPERATOR_USER_POOL_ID=<operator_user_pool_id>
#   COGNITO_OPERATOR_APP_CLIENT_ID=<operator_app_client_id>

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
