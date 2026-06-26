create table projects (
  id String,
  organization_id String,
  name String,
  timezone String
) engine = MergeTree
order by id;

create table sessions (
  project_id String,
  session_id String,
  user_id String,
  started_at DateTime
) engine = MergeTree
order by (project_id, started_at, session_id);

create table events (
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

create materialized view events_mv
engine = AggregatingMergeTree
order by (project_id, event_name, day)
as
select
  project_id,
  event_name,
  toDate(event_time) as day,
  countState() as events_state,
  uniqExactState(user_id) as users_state
from events
group by project_id, event_name, day;

-- ClickHouse row policies filter rows visible to users or roles. This fixture
-- treats them as containment only for read-only users, matching the benchmark
-- threat model rather than a general authorization boundary.
create row policy project_scope_events on events
using project_id = currentUser()
to policystrata_readonly;

create row policy project_scope_sessions on sessions
using project_id = currentUser()
to policystrata_readonly;
