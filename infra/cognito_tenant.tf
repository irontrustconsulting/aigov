# Resolves the AWS account ID at plan/apply time so the SES source ARN below
# stays portable across accounts (staging, prod) without hardcoding.
data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------------------
# Tenant (customer) Cognito user pool.
#
# This pool was originally hand-created outside Terraform (no IaC managed it
# before UI-F0-FOUNDATION). The resource blocks below are written to mirror
# the LIVE pool's actual configuration exactly — confirmed via
# `aws cognito-idp describe-user-pool` / `describe-user-pool-client` against
# eu-west-2_yW42jUA1i — so that `terraform import` followed by `terraform
# plan` shows ONLY the new OAuth/PKCE/domain fields as additions, nothing
# destructive.
#
# DO NOT apply this file before running the import commands below — applying
# against an unimported resource address would try to CREATE a second, new
# pool rather than adopt the existing one.
#
#   cd infra
#   terraform import aws_cognito_user_pool.tenants eu-west-2_yW42jUA1i
#   terraform import aws_cognito_user_pool_client.irontrustai_web \
#     eu-west-2_yW42jUA1i/42uagvtq851nehb5hsnjob3e4n
#   terraform plan   # must show ONLY additive OAuth/domain fields — stop and
#                     # reconcile this file against live values if anything
#                     # else diffs (in particular: a custom-attribute `schema`
#                     # mismatch shows as a destroy/recreate — never apply that)
#   terraform apply  # your call, after reviewing the plan
# ---------------------------------------------------------------------------

resource "aws_cognito_user_pool" "tenants" {
  name = "irontrustai-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Live config: standard self-signup is enabled on this pool (unlike the
  # operator pool, which is admin-create-only). This predates F0 and is left
  # unchanged here — out of scope for this sprint to revisit.
  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  mfa_configuration = "OFF"

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # The three custom claims verify_cognito_token reads (app/auth/cognito.py):
  # custom:tenant_id (DB tenant id), custom:role, plus custom:org_id (unused
  # by the verifier today, kept as-is from the live schema). Custom-attribute
  # shape is immutable in Cognito once created — these three blocks must match
  # the live schema exactly, or the import will show a destroy/recreate diff.
  schema {
    name                     = "org_id"
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    required                 = false
  }
  schema {
    name                     = "role"
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    required                 = false
  }
  schema {
    name                     = "tenant_id"
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    required                 = false
  }

  # Live value is INACTIVE (unlike the operator pool's ACTIVE) — left as-is,
  # not a F0 decision to change.
  deletion_protection = "INACTIVE"

  # Use our own SES-verified domain rather than Cognito's shared default sender
  # (no-reply@verificationemail.com). COGNITO_DEFAULT has poor deliverability
  # with Gmail — shared-sender reputation from unrelated AWS customers causes
  # invite emails to be silently filtered. irontrustconsulting.co.uk is a
  # verified SES domain identity in the same region; Cognito sends on its behalf
  # using DKIM, which satisfies Gmail's DMARC alignment requirements.
  email_configuration {
    email_sending_account = "DEVELOPER"
    from_email_address    = "IronTrust <info@irontrustconsulting.co.uk>"
    source_arn            = "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/irontrustconsulting.co.uk"
  }

  # Custom-attribute schema is immutable in Cognito once created, and the
  # provider's TypeSet diffing on `schema` is order-sensitive on import — a
  # post-import plan can show identical blocks as remove+add even with zero
  # real content change. Since this sprint never intends to alter the schema,
  # ignore drift here rather than risk an apply attempting to touch immutable
  # attributes on the live, in-use pool.
  lifecycle {
    ignore_changes = [schema]
  }
}

resource "aws_cognito_user_pool_client" "irontrustai_web" {
  name         = "irontrustai-web"
  user_pool_id = aws_cognito_user_pool.tenants.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH",
  ]

  # OAuth authorization-code + PKCE flow for the tenant app BFF
  # (UI-F0-FOUNDATION, FE-2/D-36). Additive alongside the existing auth flows
  # above, not a replacement.
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]

  # Dev-origin callback/logout URLs for the tenant Next app (apps/tenant, port
  # 3000 by convention — matches the operator app's 3001 in cognito_operator.tf).
  # Add the staging/prod origins here as those environments are stood up.
  callback_urls = ["http://localhost:3000/api/auth/callback"]
  logout_urls   = ["http://localhost:3000/"]

  enable_token_revocation = true

  refresh_token_validity = 30 # days
  access_token_validity  = 1  # hour
  id_token_validity      = 1  # hour

  token_validity_units {
    refresh_token = "days"
    access_token  = "hours"
    id_token      = "hours"
  }

  # `generate_secret` cannot be read back from DescribeUserPoolClient, so
  # `terraform import` leaves it unset in state — a subsequent plan then
  # treats the configured `false` as a change FROM unset, and this attribute
  # is provider-documented as force-new. Without this, `terraform apply`
  # would destroy and recreate the live client (new client id), breaking the
  # app's existing config and any live sessions. The real value has not
  # changed (confirmed via live describe: no ClientSecret on this client) —
  # ignore it rather than risk a replace.
  lifecycle {
    ignore_changes = [generate_secret]
  }
}

# Hosted-UI domain — required for the authorization-code/PKCE redirect
# endpoint to exist at all. Domain must be globally unique in the region.
resource "aws_cognito_user_pool_domain" "tenants" {
  domain       = "irontrustai-users-${var.environment}"
  user_pool_id = aws_cognito_user_pool.tenants.id
}
