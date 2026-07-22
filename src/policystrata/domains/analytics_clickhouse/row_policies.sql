-- Real ClickHouse row-policy fixture for the analytics_clickhouse domain.
-- schema.sql stays the simulated benchmark fixture; this file is the runnable
-- equivalent: it recreates the tables, a read-only role, per-project users,
-- and the project-scope row policies against a real server. As in schema.sql,
-- row policies are containment for read-only users only, matching the
-- benchmark threat model rather than a general authorization boundary.

create database if not exists policystrata;

drop table if exists policystrata.events_mv;
drop table if exists policystrata.events;
drop table if exists policystrata.sessions;
drop table if exists policystrata.projects;

create table policystrata.projects (
  id String,
  organization_id String,
  name String,
  timezone String
) engine = MergeTree
order by id;

create table policystrata.sessions (
  project_id String,
  session_id String,
  user_id String,
  started_at DateTime
) engine = MergeTree
order by (project_id, started_at, session_id);

create table policystrata.events (
  project_id String,
  legacy_project_id String,
  event_id String,
  session_id String,
  user_id String,
  event_name String,
  cohort_id String,
  country LowCardinality(String),
  platform LowCardinality(String),
  event_time DateTime
) engine = MergeTree
order by (project_id, event_time, event_name);

create materialized view policystrata.events_mv
engine = AggregatingMergeTree
order by (project_id, event_name, day)
as
select
  project_id,
  event_name,
  toDate(event_time) as day,
  countState() as events_state,
  uniqExactState(user_id) as users_state
from policystrata.events
group by project_id, event_name, day;

create role if not exists policystrata_readonly;

grant select on policystrata.projects to policystrata_readonly;
grant select on policystrata.sessions to policystrata_readonly;
grant select on policystrata.events to policystrata_readonly;
-- events_mv stays ungranted on purpose: reading the aggregate target directly
-- would bypass the row policies on events.

-- The policy predicate matches schema.sql: currentUser() is the project id, so
-- each scoped read-only user is named after its project. policystrata_unscoped
-- holds the role but matches no project and must see no rows. Passwords equal
-- user names, mirroring the support_saas policystrata_app convention.
create user if not exists project_acme_mobile identified by 'project_acme_mobile';
create user if not exists project_beta_web identified by 'project_beta_web';
create user if not exists policystrata_unscoped identified by 'policystrata_unscoped';

grant policystrata_readonly to project_acme_mobile, project_beta_web, policystrata_unscoped;

drop row policy if exists project_scope_events on policystrata.events;
create row policy project_scope_events on policystrata.events
using project_id = currentUser()
to policystrata_readonly;

drop row policy if exists project_scope_sessions on policystrata.sessions;
create row policy project_scope_sessions on policystrata.sessions
using project_id = currentUser()
to policystrata_readonly;

-- Once any row policy exists on a table, users not covered by one see no rows.
-- These catch-all policies keep the admin user able to seed and verify totals.
drop row policy if exists admin_all_events on policystrata.events;
create row policy admin_all_events on policystrata.events
using 1
to policystrata;

drop row policy if exists admin_all_sessions on policystrata.sessions;
create row policy admin_all_sessions on policystrata.sessions
using 1
to policystrata;
