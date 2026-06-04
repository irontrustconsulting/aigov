#!/bin/bash
# Runs ONCE, on first initialization of the Postgres data volume, as the
# bootstrap superuser ($POSTGRES_USER). Creates the restricted runtime role
# the application connects as.
#
# Role separation:
#   $POSTGRES_USER (e.g. aigov_admin)  -> owner / migrations / DDL. Superuser in dev.
#   app_runtime                        -> the running app. DML only, NOBYPASSRLS.
#
# Why NOBYPASSRLS matters: superusers and BYPASSRLS roles IGNORE Row-Level
# Security. If the app connected as the superuser, every tenant-isolation
# policy would be silently void. The app MUST connect as a role that RLS binds.
#
# The password is injected from the container env var APP_RUNTIME_PASSWORD so it
# is not hardcoded in source. It must match the password in the app's
# DATABASE_URL.

#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE ${APP_ROLE} WITH LOGIN PASSWORD '${APP_RUNTIME_PASSWORD}'
        NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

    GRANT USAGE ON SCHEMA public TO ${APP_ROLE};

    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ${APP_ROLE};
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ${APP_ROLE};

    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${APP_ROLE};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO ${APP_ROLE};
    
EOSQL

echo "${APP_ROLE}  rolescreated."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL

-- Dedicated identity-resolution role: sees across tenants (BYPASSRLS) but is
    -- fenced to read-only on the three identity tables by its grants alone.
    CREATE ROLE ${APP_RESOLVER_ROLE} LOGIN PASSWORD '${RESOLVER_DB_PASSWORD}' BYPASSRLS;

    -- The ONLY grants — this is what fences BYPASSRLS to identity resolution.
    GRANT SELECT ON app_user, tenant, membership TO irontrustai_resolver;

    -- It needs to connect and see the schema:
    GRANT CONNECT ON DATABASE irontrustai TO irontrustai_resolver;
    GRANT USAGE ON SCHEMA public TO irontrustai_resolver;

echo "${APP_RESOLVER_ROLE} roles created."

EOSQL

# --- Provisioner role: stands up new tenants (sales-led provisioning) ---
#
# One job only: create a new tenant and its first owner. Invoked solely by the
# platform-admin provisioning path, through its own connection/engine (exactly
# like the resolver), never by normal request handling.
#
# Why BYPASSRLS: provisioning creates a tenant that has no context yet, so the
# INSERTs can't satisfy tenant-scoped RLS. As with the resolver, the bypass is
# made safe by GRANTS, not RLS — the role is granted privileges on only the
# three identity tables, so BYPASSRLS buys it nothing anywhere else
# (no privilege = no access).
#
# Why SELECT/INSERT only (no UPDATE/DELETE) and explicit table grants (NOT
# ALTER DEFAULT PRIVILEGES like app_runtime): this role only ever *creates*.
# It must not modify or remove identity rows, and must not silently inherit
# rights on future tables. Least privilege, scoped by hand.
#
# Password from env var PROVISIONER_PASSWORD; must match the provisioner URL in
# app config. Never hardcoded, never committed.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE ${PROVISIONER_DB_USER} WITH LOGIN PASSWORD '${PROVISIONER_DB_PASSWORD}'
        NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS;

    GRANT USAGE ON SCHEMA public TO irontrustai_provisioner;

    -- Create-and-read on the three identity tables, and ONLY those.
    GRANT SELECT, INSERT ON tenant, app_user, membership TO irontrustai_provisioner;
EOSQL

echo "irontrustai_provisioner role created."