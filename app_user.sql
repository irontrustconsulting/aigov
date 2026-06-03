-- Manual test-data provisioning: create John Doyle's app_user and his
-- membership in Acme Corp, so the authorisation chain has DB records to
-- resolve against. This is what the onboarding flow will later automate.
--
-- Run as the admin role (it writes identity tables; these are global, and
-- creating them is an administrative/onboarding act):
--   docker compose exec postgres psql -U irontrustai_admin -d irontrustai -f /path/to/this.sql
-- or paste into a psql session.
--
-- Values from the test user's verified token:
--   sub        = 36229204-50c1-707a-e18e-c42e10ede8b0
--   email      = maosaherbert@gmail.com
--   name       = John Doyle
--   tenant_id  = 6be51846-1261-489b-b55f-cb4d6b2e3fcc   (Acme Corp, already in DB)
--   role       = org_admin  (we store the membership role; adjust enum value if needed)

-- 1. The app_user, keyed on the Cognito sub.
INSERT INTO app_user (id, cognito_sub, email, display_name)
VALUES (gen_random_uuid(),
        '36229204-50c1-707a-e18e-c42e10ede8b0',
        'maosaherbert@gmail.com',
        'John Doyle')
ON CONFLICT (cognito_sub) DO NOTHING;

-- 2. The membership linking that user to Acme Corp.
--    NOTE: membership.role is the user_role enum. Its STORED values are the
--    member NAMES (uppercase): ADMIN | REVIEWER | CONTRIBUTOR | AUDITOR_READONLY.
--    The token's custom:role is 'org_admin' (Cognito's label) — map it to your
--    enum here. Using ADMIN as the equivalent of org_admin.
INSERT INTO membership (id, user_id, tenant_id, role)
SELECT gen_random_uuid(), u.id, '6be51846-1261-489b-b55f-cb4d6b2e3fcc', 'ADMIN'
FROM app_user u
WHERE u.cognito_sub = '36229204-50c1-707a-e18e-c42e10ede8b0'
ON CONFLICT (user_id, tenant_id) DO NOTHING;

-- Verify:
--   SELECT u.display_name, t.name AS tenant, m.role
--   FROM membership m
--   JOIN app_user u ON u.id = m.user_id
--   JOIN tenant t ON t.id = m.tenant_id
--   WHERE u.cognito_sub = '36229204-50c1-707a-e18e-c42e10ede8b0';
