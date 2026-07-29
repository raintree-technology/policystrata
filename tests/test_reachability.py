import json
import sys
from pathlib import Path

import pytest

from policystrata.domain import load_policy, load_surface_config
from policystrata.generator import mutation_ids_for_domain, select_restricted_principal
from policystrata.models import SemanticQuery, WitnessClass
from policystrata.reachability import (
    DEFAULT_ANTHROPIC_MODEL,
    AnthropicClient,
    DeterministicStubClient,
    ReachabilityBudget,
    ReachabilityCase,
    ReachabilityReport,
    build_cases,
    generate_paraphrases,
    parse_semantic_query,
    render_manifest_prompt,
    run_manifest_skew_probe,
    run_reachability_study,
    stale_alias_entries,
    system_prompt_for_case,
    write_reachability_report,
)

DOMAIN = "support_saas"

ALLOWED_QUERY_JSON = json.dumps(
    {
        "metric": "ticket_count",
        "dimensions": ["month"],
        "filters": {},
        "time_range": "last_month",
        "grain": "month",
        "limit": 100,
    }
)


def stale_alias_case(paraphrase_count: int = 1) -> ReachabilityCase:
    cases = build_cases(
        DOMAIN,
        paraphrase_count=paraphrase_count,
        mutations=["stale_metric_alias_manifest"],
    )
    assert len(cases) == 1
    return cases[0]


def test_build_cases_covers_all_domain_mutations() -> None:
    cases = build_cases(DOMAIN, paraphrase_count=2)
    assert [case.mutation for case in cases] == mutation_ids_for_domain(DOMAIN)
    for case in cases:
        assert len(case.paraphrases) == 2
        assert case.id == f"{case.mutation}_reachability"
        assert case.expected_witness_class != WitnessClass.CLEAN


def test_generate_paraphrases_is_deterministic_and_bounded() -> None:
    query = SemanticQuery(metric="net_revenue", dimensions=["region"], time_range="last_month")
    first = generate_paraphrases(query, count=4, seed=7)
    second = generate_paraphrases(query, count=4, seed=7)
    other_seed = generate_paraphrases(query, count=4, seed=8)
    assert first == second
    assert len(first) == len(set(first)) == 4
    assert first != other_seed
    assert all("net revenue" in paraphrase for paraphrase in first)
    with pytest.raises(ValueError):
        generate_paraphrases(query, count=0, seed=7)
    with pytest.raises(ValueError):
        generate_paraphrases(query, count=99, seed=7)


def test_hand_written_paraphrase_files_take_precedence(tmp_path: Path) -> None:
    paraphrase_dir = tmp_path / "paraphrases"
    paraphrase_dir.mkdir()
    (paraphrase_dir / "stale_metric_alias_manifest.txt").write_text(
        "# reviewer-authored paraphrases\n"
        "Show bookings by month for last month.\n"
        "\n"
        "What were our bookings by region for last month?\n",
        encoding="utf-8",
    )
    cases = build_cases(
        DOMAIN,
        paraphrase_count=3,
        paraphrase_dir=paraphrase_dir,
        mutations=["stale_metric_alias_manifest", "gross_net_metric_drift"],
    )
    assert cases[0].paraphrases == [
        "Show bookings by month for last month.",
        "What were our bookings by region for last month?",
    ]
    assert len(cases[1].paraphrases) == 3


def test_manifest_prompt_hides_and_exposes_stale_aliases() -> None:
    policy = load_policy(DOMAIN)
    principal = select_restricted_principal(policy)
    assert stale_alias_entries(policy, principal.role) == ["bookings", "gross_bookings"]
    current = render_manifest_prompt(policy, principal, manifest_version="v7")
    skewed = render_manifest_prompt(
        policy, principal, manifest_version="v7-stale", include_stale_aliases=True
    )
    assert "metric bookings" not in current
    assert "metric bookings" in skewed
    assert "metric ticket_count" in current


def test_stub_reaches_stale_alias_case() -> None:
    case = stale_alias_case()
    report = run_reachability_study(DeterministicStubClient(), [case], ReachabilityBudget())

    assert report.total_cases == 1
    assert report.reached_cases == 1
    result = report.results[0]
    assert result.reached
    outcome = result.outcomes[0]
    assert outcome.parsed
    assert outcome.attempts == 1
    assert outcome.emitted_query is not None
    assert outcome.emitted_query.metric == "bookings"
    assert outcome.observed_witness_class == WitnessClass.OVER_PERMISSIVE
    assert outcome.observed_localized_surface == "manifest"


def test_scripted_allowed_query_does_not_reach_drift() -> None:
    case = stale_alias_case()
    client = DeterministicStubClient(scripted=[ALLOWED_QUERY_JSON])
    report = run_reachability_study(client, [case], ReachabilityBudget())

    result = report.results[0]
    assert not result.reached
    assert report.reached_cases == 0
    outcome = result.outcomes[0]
    assert outcome.parsed
    assert outcome.observed_witness_class == WitnessClass.CLEAN
    assert not outcome.reached


def test_repair_budget_recovers_from_malformed_reply() -> None:
    case = stale_alias_case()
    client = DeterministicStubClient(malformed_prefix=1)
    report = run_reachability_study(client, [case], ReachabilityBudget(max_attempts=3))

    outcome = report.results[0].outcomes[0]
    assert outcome.parsed
    assert outcome.attempts == 2
    assert outcome.reached
    assert len(client.calls) == 2
    assert "not a valid semantic-query" in client.calls[1][1]


def test_repair_budget_exhaustion_marks_paraphrase_unparsed() -> None:
    case = stale_alias_case()
    client = DeterministicStubClient(malformed_prefix=10)
    report = run_reachability_study(client, [case], ReachabilityBudget(max_attempts=2))

    result = report.results[0]
    outcome = result.outcomes[0]
    assert not outcome.parsed
    assert outcome.attempts == 2
    assert outcome.error is not None
    assert not outcome.reached
    assert not result.reached
    assert len(client.calls) == 2


def test_stale_alias_case_uses_skewed_manifest_prompt() -> None:
    policy = load_policy(DOMAIN)
    surface_config = load_surface_config(DOMAIN)
    principal = select_restricted_principal(policy)
    from policystrata.mutations import get_mutation

    skewed = system_prompt_for_case(
        policy, principal, get_mutation("stale_metric_alias_manifest"), surface_config
    )
    unskewed = system_prompt_for_case(
        policy, principal, get_mutation("gross_net_metric_drift"), surface_config
    )
    assert "metric bookings" in skewed
    assert "v7-stale" in skewed
    assert "metric bookings" not in unskewed


def test_manifest_skew_probe_detects_differing_plans() -> None:
    probe = run_manifest_skew_probe(DeterministicStubClient(), domain=DOMAIN)

    assert probe.stale_alias == "bookings"
    assert probe.current_query is not None
    assert probe.skewed_query is not None
    assert probe.skewed_query.metric == "bookings"
    assert probe.current_query.metric != "bookings"
    assert probe.plans_differ


def test_full_stub_study_over_domain_and_report_serialization(tmp_path: Path) -> None:
    cases = build_cases(DOMAIN, paraphrase_count=2)
    budget = ReachabilityBudget(max_attempts=2)
    client = DeterministicStubClient()
    report = run_reachability_study(client, cases, budget)
    probe = run_manifest_skew_probe(client, domain=DOMAIN, budget=budget)
    report = report.model_copy(update={"skew_probe": probe})

    assert report.client == "deterministic-stub"
    assert report.total_cases == len(mutation_ids_for_domain(DOMAIN))
    assert report.reached_cases == sum(1 for result in report.results if result.reached)
    by_mutation = {result.mutation: result for result in report.results}
    assert by_mutation["stale_metric_alias_manifest"].reached
    assert by_mutation["db_rls_old_ownership_field"].reached
    assert by_mutation["cost_estimate_ignores_expansion"].reached
    for result in report.results:
        assert result.paraphrase_count == 2
        assert result.total_attempts >= 2

    report_path = write_reachability_report(report, tmp_path / "out")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    restored = ReachabilityReport.model_validate(payload)
    assert restored.total_cases == report.total_cases
    assert restored.reached_cases == report.reached_cases
    assert restored.skew_probe is not None
    assert restored.skew_probe.plans_differ == probe.plans_differ
    assert restored.results[0].outcomes[0].paraphrase == report.results[0].outcomes[0].paraphrase


def test_parse_semantic_query_accepts_fenced_json_and_rejects_junk() -> None:
    fenced = f"```json\n{ALLOWED_QUERY_JSON}\n```"
    query = parse_semantic_query(fenced)
    assert query.metric == "ticket_count"
    with pytest.raises(ValueError):
        parse_semantic_query("no json here")
    with pytest.raises(ValueError):
        parse_semantic_query('{"metric": "ticket_count", "limit": 0}')


def test_anthropic_client_reports_missing_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unused")
    client = AnthropicClient()
    with pytest.raises(RuntimeError, match="anthropic"):
        client.complete("system", "prompt")


def test_anthropic_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyModule:
        @staticmethod
        def Anthropic(api_key: str) -> None:  # noqa: N802 - mirrors the SDK name
            raise AssertionError("must not construct a client without an API key")

    monkeypatch.setitem(sys.modules, "anthropic", DummyModule())
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = AnthropicClient()
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        client.complete("system", "prompt")


def test_anthropic_client_model_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POLICYSTRATA_REACHABILITY_MODEL", raising=False)
    assert AnthropicClient().model == DEFAULT_ANTHROPIC_MODEL
    monkeypatch.setenv("POLICYSTRATA_REACHABILITY_MODEL", "claude-example-override")
    assert AnthropicClient().model == "claude-example-override"
    assert AnthropicClient(model="explicit-wins").model == "explicit-wins"
    assert AnthropicClient().name == "anthropic:claude-example-override"
