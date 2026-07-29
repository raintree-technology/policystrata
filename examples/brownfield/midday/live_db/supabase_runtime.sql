-- SYNTHESIZED. Not midday's code.
--
-- midday's committed migrations assume a Supabase-managed base schema: the roles its GRANTs
-- name, the auth/private functions its RLS predicates call, and the base tables its in-scope
-- tables reference by foreign key. None of that lives in packages/db/migrations, so none of it
-- can be copied from the repository. This file supplies the smallest bridge that lets midday's
-- real, unmodified CREATE POLICY statements load and take effect in stock PostgreSQL.
--
-- Every object here is invented by Raintree. Read every finding produced against this fixture as
-- evidence about midday's real *policy text* executing under a reconstructed runtime, not as
-- evidence about midday's deployed Supabase runtime, which we have never observed.
--
-- The one binding that matters for the evidence: PolicyStrata sets app.tenant_id per check
-- (src/policystrata/database.py), and auth.uid() below reads it. So "app.tenant_id = <uuid>"
-- means "the request is authenticated as that user", and midday's own predicates decide the
-- rest without being touched.

CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS private;

-- Supabase's standard role set. midday's real GRANT and CREATE POLICY statements name these.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN;
  END IF;
END
$$;

-- midday_app is a PolicyStrata harness role, not part of Supabase. The evidence runner provisions
-- it at cluster scope before loading this bridge. Keeping that side effect in the runner makes the
-- native/runtime boundary explicit and lets a shared test cluster reuse an existing namespaced
-- role without this SQL altering its login properties.
-- PostgreSQL 16 stores inheritance on the membership as well as the member role. State it
-- explicitly so a reused fixture role cannot retain a historical NOINHERIT membership.
GRANT authenticated TO midday_app WITH INHERIT TRUE;

-- Reconstruction of Supabase's auth.uid(). The real implementation reads the verified JWT
-- claim; this reads the session setting PolicyStrata controls, which is what makes the
-- containment matrix expressible.
CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid
$$;

-- Base tables midday's in-scope tables reference by foreign key. Column sets are the minimum
-- the references need, not midday's real definitions.
CREATE TABLE IF NOT EXISTS teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoice_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE
);

-- Team membership. midday's real RLS predicate is
--   team_id IN (SELECT private.get_teams_for_authenticated_user())
-- so the function has to resolve a user to their teams through a join table of this shape.
CREATE TABLE IF NOT EXISTS users_on_team (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, team_id)
);

-- SECURITY DEFINER matches the Supabase pattern: the lookup itself must not be subject to the
-- policies it is used to evaluate, or the predicate would recurse.
CREATE OR REPLACE FUNCTION private.get_teams_for_authenticated_user()
RETURNS SETOF uuid
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  SELECT team_id FROM users_on_team WHERE user_id = auth.uid()
$$;

-- Realtime publication referenced by midday's migrations.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
    CREATE PUBLICATION supabase_realtime;
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public, auth, private TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION private.get_teams_for_authenticated_user() TO anon, authenticated, service_role;
GRANT SELECT ON teams, users, customers, invoice_templates, users_on_team TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO authenticated;
