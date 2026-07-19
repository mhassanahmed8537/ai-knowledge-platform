-- Cluster-level role bootstrap for local development.
--
-- These roles are created once against the local Postgres. In AWS they are
-- provisioned by Terraform / managed via IAM database auth, NOT by this script.
--
--   app_user : runtime, least-privilege, RLS-ENFORCED (no BYPASSRLS).
--   app_auth : trusted auth subsystem only, BYPASSRLS (login/signup/refresh/oauth).
--
-- Table- and row-level grants/policies are applied by the Alembic RLS migration,
-- which must run AFTER these roles exist.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN PASSWORD 'app_password' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_auth') THEN
        CREATE ROLE app_auth LOGIN PASSWORD 'auth_password' NOSUPERUSER BYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE knowledge_platform TO app_user, app_auth;
GRANT USAGE ON SCHEMA public TO app_user, app_auth;
