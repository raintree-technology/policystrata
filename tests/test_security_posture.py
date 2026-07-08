from __future__ import annotations

import re
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
