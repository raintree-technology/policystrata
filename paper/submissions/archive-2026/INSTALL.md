# Install And Run

## 1. Confirm Layout

```bash
pwd
ls
ls ../policystrata
```

Expected layout:

```text
workspace/
  papers/conference-kit/
  policystrata/
```

## 2. Run The 30-Minute Smoke Test

```bash
cd ../policystrata
rm -rf runs/conference-kit-smoke
uv run policystrata run --domain support_saas --suite seeded --out runs/conference-kit-smoke/seeded
uv run policystrata evidence seeded=runs/conference-kit-smoke/seeded --out runs/conference-kit-smoke/evidence.md
grep -q "| seeded | 50 | 50 | 0 |" runs/conference-kit-smoke/evidence.md
```

Success means the seeded deterministic suite reports 50 mutants, 50 killed, and 0 survived.

## 3. Run Full Deterministic Reproduction

```bash
cd ../papers/conference-kit
./reproduce-final.sh
```

The script writes evidence to:

```text
../policystrata/runs/final/evidence.md
```

`./reproduce.sh` remains available as a shorter compatibility check for the earlier 620-case suite.

## 4. Optional PostgreSQL/RLS Smoke Test

```bash
cd ../policystrata
docker compose -f ../papers/conference-kit/docker-compose.yml up -d postgres
POLICYSTRATA_RUN_DB_TESTS=1 uv run --extra dev pytest tests/test_postgres_integration.py
docker compose -f ../papers/conference-kit/docker-compose.yml down
```

This database smoke test is not part of the 1720-case deterministic score.

## 5. Optional ClickHouse Smoke Test

```bash
cd ../policystrata
docker compose -f ../papers/conference-kit/docker-compose.yml up -d clickhouse
POLICYSTRATA_RUN_CLICKHOUSE_TESTS=1 uv run --extra dev pytest tests/test_clickhouse_integration.py
docker compose -f ../papers/conference-kit/docker-compose.yml down
```

The deterministic ClickHouse-style analytics domain does not require this live service.
