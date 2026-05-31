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

echo "${APP_ROLE} role created."