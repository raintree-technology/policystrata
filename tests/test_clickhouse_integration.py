import os
from pathlib import Path

import pytest

from policystrata.database_clickhouse import ClickHouseAdapter, fixture_reader

pytestmark = pytest.mark.integration

DOMAIN_ROOT = Path("src/policystrata/domains/analytics_clickhouse")


def load_row_policy_fixture() -> ClickHouseAdapter:
    admin = ClickHouseAdapter()
    admin.execute_script(DOMAIN_ROOT / "row_policies.sql")
    admin.execute_script(DOMAIN_ROOT / "seed.sql")
    return admin


@pytest.mark.skipif(
    os.environ.get("POLICYSTRATA_RUN_CLICKHOUSE_TESTS") != "1",
    reason="set POLICYSTRATA_RUN_CLICKHOUSE_TESTS=1 and start docker compose clickhouse",
)
def test_clickhouse_service_smoke() -> None:
    adapter = ClickHouseAdapter()
    rows = adapter.query("select 1 as one")

    assert rows == [{"one": 1}]


@pytest.mark.skipif(
    os.environ.get("POLICYSTRATA_RUN_CLICKHOUSE_TESTS") != "1",
    reason="set POLICYSTRATA_RUN_CLICKHOUSE_TESTS=1 and start docker compose clickhouse",
)
def test_clickhouse_row_policy_scopes_project_rows() -> None:
    load_row_policy_fixture()

    reader = fixture_reader("project_acme_mobile")
    events = reader.query("select project_id, event_name from events order by event_time")
    sessions = reader.query("select project_id, session_id from sessions order by session_id")

    assert len(events) == 4
    assert {row["project_id"] for row in events} == {"project_acme_mobile"}
    assert len(sessions) == 3
    assert {row["project_id"] for row in sessions} == {"project_acme_mobile"}


@pytest.mark.skipif(
    os.environ.get("POLICYSTRATA_RUN_CLICKHOUSE_TESTS") != "1",
    reason="set POLICYSTRATA_RUN_CLICKHOUSE_TESTS=1 and start docker compose clickhouse",
)
def test_clickhouse_other_and_unscoped_readers_stay_contained() -> None:
    load_row_policy_fixture()

    beta = fixture_reader("project_beta_web")
    beta_events = beta.query("select project_id, event_name from events order by event_time")
    unscoped = fixture_reader("policystrata_unscoped")
    unscoped_events = unscoped.query("select project_id from events")

    assert len(beta_events) == 1
    assert {row["project_id"] for row in beta_events} == {"project_beta_web"}
    assert unscoped_events == []


@pytest.mark.skipif(
    os.environ.get("POLICYSTRATA_RUN_CLICKHOUSE_TESTS") != "1",
    reason="set POLICYSTRATA_RUN_CLICKHOUSE_TESTS=1 and start docker compose clickhouse",
)
def test_clickhouse_missing_row_policy_is_observed_as_over_exposure() -> None:
    admin = load_row_policy_fixture()
    admin.execute_statement("drop row policy if exists project_scope_events on policystrata.events")
    admin.execute_statement("drop row policy if exists admin_all_events on policystrata.events")

    reader = fixture_reader("project_acme_mobile")
    exposed = reader.query("select project_id from events")

    # Restore the fixture before asserting so a failure does not leave the
    # shared service without policies.
    load_row_policy_fixture()

    assert len(exposed) == 5
    assert {row["project_id"] for row in exposed} == {"project_acme_mobile", "project_beta_web"}
