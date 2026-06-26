import os
import urllib.error
import urllib.request

import pytest


@pytest.mark.integration
def test_optional_clickhouse_service_smoke() -> None:
    if os.environ.get("POLICYSTRATA_RUN_CLICKHOUSE_TESTS") != "1":
        pytest.skip("set POLICYSTRATA_RUN_CLICKHOUSE_TESTS=1 to run optional ClickHouse smoke test")

    url = os.environ.get("POLICYSTRATA_CLICKHOUSE_URL", "http://localhost:8123/")
    request = urllib.request.Request(url, data=b"select 1", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8").strip()
    except urllib.error.URLError as exc:
        pytest.fail(f"ClickHouse service is not reachable at {url}: {exc}")

    assert body == "1"
