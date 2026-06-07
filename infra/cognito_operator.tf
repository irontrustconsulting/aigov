# ---------------------------------------------------------------------------
# Operator (platform-staff) Cognito user pool.
#
# This pool answers ONE question: "who is this staff member?" (authentication).
# It carries NO authorization on purpose:
#   - no custom:tenant_id  -> operators are not members of any tenant
#   - no role attribute    -> what an operator may do lives in the DATABASE,
#                             per the Cognito-authN / DB-authZ split.
# So it is a plainer pool than the customer one.
# ---------------------------------------------------------------------------

resource "aws_cognito_user_pool" "operators" {
  name = "irontrustai-operators-${var.environment}"

  # Staff sign in with their email address as the username.
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Only an admin (our CLI calling AdminCreateUser) can create operators. This
  # switches OFF public self-signup entirely — there is no "register" path into
  # this pool. It is the Terraform expression of "operators are created, never
  # self-registered."
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  # MFA required for every operator (agreed: privileged identities, MFA from
  # day one). We use TOTP / authenticator-app MFA (software token) rather than
  # SMS: no per-message cost, no phone-number handling, and stronger.
  mfa_configuration = "ON"
  software_token_mfa_configuration {
    enabled = true
  }

  # Tighter than a consumer default because these are privileged accounts.
  password_policy {
    minimum_length                   = 14
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 3 # the invite must be used promptly
  }

  # Account recovery via verified email only.
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Guard against an accidental `terraform destroy` wiping the staff identity
  # store. To tear it down deliberately you must first flip this to INACTIVE.
  deletion_protection = "ACTIVE"
}

# ---------------------------------------------------------------------------
# App client = the door operators LOG IN through.
#
# The operator UI console (and, as a fallback, a CLI or test harness) uses this
# client to authenticate an operator and obtain tokens. It is NOT used to CREATE
# operators (that is the AdminCreateUser admin API), and our BACKEND does NOT use
# it to VERIFY tokens (verification needs only the pool's JWKS public keys plus
# this client id, checked as the `aud` claim). This client is purely about token
# ISSUANCE — logging an existing operator in.
# ---------------------------------------------------------------------------

resource "aws_cognito_user_pool_client" "operator_console" {
  name         = "irontrustai-operator-console-${var.environment}"
  user_pool_id = aws_cognito_user_pool.operators.id

  # Public client (no secret), SRP login. A deliberate least-regret default: it
  # works for a browser SPA console (via the Cognito JS SDK) AND for a boto3
  # test-harness login today, with no client secret to manage.
  #
  # DEFERRED (a console-login-UX decision, not needed yet):
  #   - To use the Cognito Hosted UI with the OAuth authorization-code flow, add
  #     allowed_oauth_flows / callback_urls / a user-pool domain later. That is
  #     an in-place UPDATE to this client.
  #   - To use a confidential server-side client, set generate_secret = true.
  #     That forces a client REPLACEMENT, so decide before prod.
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",      # secure challenge-response login (no password on the wire)
    "ALLOW_REFRESH_TOKEN_AUTH", # refresh without re-entering the password
  ]

  # On a failed login, don't reveal whether the email exists in the pool.
  prevent_user_existence_errors = "ENABLED"

  # Short-lived access/id tokens; longer refresh.
  id_token_validity      = 60 # minutes
  access_token_validity  = 60 # minutes
  refresh_token_validity = 8  # hours

  token_validity_units {
    id_token      = "minutes"
    access_token  = "minutes"
    refresh_token = "hours"
  }
}
