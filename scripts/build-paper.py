#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = ROOT / "paper"
SOURCE = PAPER_DIR / "main.tex"
BUILD_DIR = PAPER_DIR / "build"
GENERATED_PDF = BUILD_DIR / "main.pdf"
OUTPUT_PDF = BUILD_DIR / "PolicyStrata.pdf"
BUILD_LOG = BUILD_DIR / "tectonic.log"
FALLBACK_SOURCE_DATE_EPOCH = "1785102000"
EXPECTED_METADATA = {
    "Title": "PolicyStrata: Responsibility-Scoped Testing for Cross-Layer Policy Drift in LLM Data Agents",
    "Author": "Zachary Roth",
    "Subject": "Responsibility-scoped testing for cross-layer policy drift in LLM data agents",
    "Keywords": "PolicyStrata, LLM data agents, policy drift, regression testing",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the canonical PolicyStrata paper.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail on unresolved references, placeholders, or layout overflow.",
    )
    return parser.parse_args()


def required_executable(name: str, environment_variable: str) -> str:
    configured = os.environ.get(environment_variable)
    if configured:
        return configured

    detected = shutil.which(name)
    if detected:
        return detected

    raise SystemExit(
        f"{name} was not found. Install it or set {environment_variable} to the executable path."
    )


def source_date_epoch() -> str:
    configured = os.environ.get("SOURCE_DATE_EPOCH")
    if configured:
        return configured

    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", "paper"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or FALLBACK_SOURCE_DATE_EPOCH


def run_tectonic() -> str:
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = source_date_epoch()
    result = subprocess.run(
        [
            required_executable("tectonic", "TECTONIC"),
            "-X",
            "compile",
            "--outdir",
            str(BUILD_DIR),
            "--outfmt",
            "pdf",
            SOURCE.name,
        ],
        cwd=PAPER_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    log = "\n".join(part for part in [result.stdout, result.stderr] if part)
    BUILD_LOG.write_text(log)
    if result.returncode:
        sys.stderr.write(log)
        raise SystemExit(result.returncode)
    return log


def normalize_pdf() -> None:
    if not GENERATED_PDF.exists():
        raise SystemExit(f"Expected build output was not created: {GENERATED_PDF}")

    subprocess.run(
        [
            required_executable("qpdf", "QPDF"),
            "--deterministic-id",
            "--object-streams=disable",
            "--stream-data=preserve",
            str(GENERATED_PDF),
            str(OUTPUT_PDF),
        ],
        check=True,
    )
    GENERATED_PDF.unlink()
    subprocess.run(
        [required_executable("qpdf", "QPDF"), "--check", str(OUTPUT_PDF)],
        check=True,
        capture_output=True,
        text=True,
    )


def pdf_page_count() -> int | None:
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        return None

    result = subprocess.run(
        [pdfinfo, str(OUTPUT_PDF)],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return None


def validate_metadata() -> None:
    pdf = OUTPUT_PDF.read_bytes().decode("latin1")
    missing = [
        f"/{key} ({value})" for key, value in EXPECTED_METADATA.items() if f"/{key} ({value})" not in pdf
    ]
    if missing:
        raise SystemExit(f"PDF metadata validation failed: {', '.join(missing)}")


def validate_strict(log: str) -> None:
    failures: list[str] = []
    lowered_log = log.lower()
    for marker in ("undefined references", "missing character"):
        if marker in lowered_log:
            failures.append(f"build log contains {marker!r}")
    if re.search(r"citation .* undefined", lowered_log):
        failures.append("build log contains an undefined citation")
    if "overfull \\hbox" in lowered_log:
        failures.append("build log contains an overfull horizontal box")

    source_files = [
        SOURCE,
        PAPER_DIR / "preamble.tex",
        PAPER_DIR / "references.bib",
        *sorted((PAPER_DIR / "sections").glob("*.tex")),
    ]
    placeholders = [
        str(path.relative_to(ROOT))
        for path in source_files
        if "TODO" in path.read_text() or "??" in path.read_text()
    ]
    if placeholders:
        failures.append(f"source placeholders remain in: {', '.join(placeholders)}")

    if failures:
        raise SystemExit("Paper validation failed:\n- " + "\n- ".join(failures))


def main() -> None:
    args = parse_args()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_PDF.unlink(missing_ok=True)
    OUTPUT_PDF.unlink(missing_ok=True)

    log = run_tectonic()
    normalize_pdf()
    validate_metadata()
    if args.check:
        validate_strict(log)

    digest = hashlib.sha256(OUTPUT_PDF.read_bytes()).hexdigest()
    pages = pdf_page_count()
    warning_lines = {
        re.sub(r"^warning: [^:]+:\d+: ", "warning: ", line)
        for line in log.splitlines()
        if line.startswith("warning:")
    }
    page_detail = f", {pages} pages" if pages is not None else ""
    print(f"{OUTPUT_PDF.relative_to(ROOT)}{page_detail}")
    print(f"sha256 {digest}")
    print(f"TeX diagnostics: {len(warning_lines)} unique warnings; log: {BUILD_LOG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
