from __future__ import annotations

import re
import subprocess
from pathlib import Path

SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\bA(?:KIA|SIA)[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "dist",
    "node_modules",
    "runs",
}
TEXT_SUFFIXES = {
    ".cff",
    ".css",
    ".env",
    ".example",
    ".gitignore",
    ".html",
    ".in",
    ".js",
    ".json",
    ".jsonl",
    ".lock",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
FIXTURE_ROOTS = (
    Path("examples"),
    Path("src/policystrata/domains"),
    Path("src/policystrata/scanner_examples"),
    Path("tests/fixtures"),
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
PRIVATE_TRACKED_PATH_PATTERNS = {
    "planning_file": re.compile(
        r"(?:^|/)[^/]*(?:todo|roadmap|milestones?|commercial-strategy|completion-audit|"
        r"review-response|production-pilot|pilot-install|distribution-decision)\.(?:md|txt)$",
        re.IGNORECASE,
    ),
    "review_working_file": re.compile(
        r"(?:^|/)paper/[^/]*(?:response|revision|demo)[^/]*\.md$",
        re.IGNORECASE,
    ),
    "submission_builder": re.compile(
        r"(?:^|/)(?:scripts/build|tests/test)[^/]*(?:anon(?:ymous)?|demo)[^/]*\.(?:py|sh|mjs)$",
        re.IGNORECASE,
    ),
}
PUBLIC_TREE_FORBIDDEN_PATTERNS = {
    "absolute_macos_user_path": re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    "legacy_product_header": re.compile("x-" + "assurance-" + "organization-id", re.IGNORECASE),
    "personal_machine_identity": re.compile(
        r"(?:zach\.accounts@|admin@rain" + r"tree|mb1s-Mac" + r"Book)",
        re.IGNORECASE,
    ),
    "private_project_identifier": re.compile(
        r"\b(?:Better" + r"Off|SEC" + r"UTE)\b",
        re.IGNORECASE,
    ),
    "private_submission_artifact": re.compile(
        r"(?:" + "submission-" + r"kit|conference-" + r"kit|Hot" + r"CRP)",
        re.IGNORECASE,
    ),
    "temporary_agent_path": re.compile("/private/tmp/" + "claude"),
    "production_deployment_id": re.compile(r"\bdpl_[A-Za-z0-9]+"),
}


def test_repository_contains_no_high_confidence_secret_patterns() -> None:
    findings: list[str] = []

    for path in Path(".").rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in {"LICENSE", "CODEOWNERS"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path}: {name}")

    assert findings == []


def test_fixture_emails_use_reserved_example_domains() -> None:
    findings: list[str] = []

    for root in FIXTURE_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in EMAIL_PATTERN.finditer(text):
                domain = match.group(1).lower()
                if not domain.endswith(".example"):
                    findings.append(f"{path}: {match.group(0)}")

    assert findings == []


def test_public_tree_excludes_private_working_material() -> None:
    public_paths = set(
        subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )
    public_files = {relative_path for relative_path in public_paths if Path(relative_path).is_file()}
    private_paths = [
        relative_path
        for relative_path in public_files
        if any(pattern.search(relative_path) for pattern in PRIVATE_TRACKED_PATH_PATTERNS.values())
    ]
    assert private_paths == []

    findings: list[str] = []
    for relative_path in sorted(public_files):
        path = Path(relative_path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in PUBLIC_TREE_FORBIDDEN_PATTERNS.items():
            if pattern.search(relative_path) or pattern.search(text):
                findings.append(f"{relative_path}: {name}")

    assert findings == []


def test_source_distribution_uses_reviewed_public_allowlists() -> None:
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")

    for top_level in ("benchmarks", "docs", "examples", "packages", "paper", "scripts", "studies", "tests"):
        assert f"include {top_level}" not in manifest
        assert f"recursive-include {top_level}" not in manifest
    for pattern in PRIVATE_TRACKED_PATH_PATTERNS.values():
        assert not pattern.search(manifest)


def test_publish_workflow_routes_release_artifacts_and_supports_safe_retries() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
    smoke = Path("scripts/release-smoke.mjs").read_text(encoding="utf-8")
    publish_pypi = workflow.split("\n  publish-pypi:", 1)[1].split("\n  publish-npm:", 1)[0]
    publish_npm = workflow.split("\n  publish-npm:", 1)[1].split("\n  publish-gateway-npm:", 1)[0]
    publish_gateway = workflow.split("\n  publish-gateway-npm:", 1)[1].split("\n  verify-pypi:", 1)[0]
    dispatch_inputs = workflow.split("\n  push:", 1)[0]

    assert "!contains(github.ref_name, '-npm.')" in workflow
    assert dispatch_inputs.count("default: false") == 6
    assert "github.event_name == 'push' || inputs.publish_pypi" in workflow
    assert "github.event_name == 'push' || inputs.publish_npm" in workflow
    assert "github.event_name == 'push' || inputs.publish_gateway_npm" in workflow
    assert workflow.count("id: npm-version") == 2
    assert workflow.count("steps.npm-version.outputs.published != 'true'") == 2
    assert workflow.count("id: pypi-version") == 1
    assert workflow.count("steps.pypi-version.outputs.published != 'true'") == 4
    assert '"https://pypi.org/pypi/${package_name}/${package_version}/json"' in workflow
    assert "verify_pypi:" in workflow
    assert "verify_npm:" in workflow
    assert "verify_gateway_npm:" in workflow
    assert "inputs.publish_pypi || inputs.verify_pypi" in workflow
    assert "inputs.publish_npm || inputs.verify_npm" in workflow
    assert "inputs.publish_gateway_npm || inputs.verify_gateway_npm" in workflow
    assert workflow.count('POLICYSTRATA_RELEASE_SMOKE_RETRIES: "15"') == 3
    assert "--published-" not in publish_pypi
    assert "--published-" not in publish_npm
    assert "--published-" not in publish_gateway
    assert 'POLICYSTRATA_RELEASE_SMOKE_RETRIES || "15"' in smoke
    assert '"--prefer-online", "--cache", cache' in smoke
    assert "npm-cache-${attempt}" in smoke
    assert "assertPythonSourceDistribution(sourceDistribution)" in smoke
    assert "source distribution contains unreviewed paths" in smoke
