#!/usr/bin/env python3
"""Build a minimal arXiv source bundle for the public PolicyStrata preprint."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
SOURCE_TEX = REPO_ROOT / "papers" / "policystrata" / "paper.tex"
SOURCE_REFS = REPO_ROOT / "papers" / "policystrata" / "refs.bib"
SOURCE_PREAMBLE = REPO_ROOT / "shared" / "preamble.tex"
BUILD_DIR = SCRIPT_DIR / "build"
SOURCE_DIR = BUILD_DIR / "policystrata-arxiv-source"
ZIP_PATH = SCRIPT_DIR / "policystrata-arxiv-source.zip"
MANIFEST_PATH = SCRIPT_DIR / "package-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_portable_tex(source: str) -> str:
    source = source.replace(r"\input{../../shared/preamble}", r"\input{preamble}")
    source = source.replace(
        r"\AtBeginDocument{\fontsize{9.55pt}{10.95pt}\selectfont}",
        r"\AtBeginDocument{\fontsize{9.05pt}{10.25pt}\selectfont}",
    )
    source = source.replace(r"\setlength{\parskip}{1.2pt}", r"\setlength{\parskip}{0.7pt}")
    source = source.replace(r"\setlength{\bibsep}{1pt plus 0.2ex}", r"\setlength{\bibsep}{0pt}")
    source = source.replace(r"\renewcommand{\bibfont}{\footnotesize}", r"\renewcommand{\bibfont}{\scriptsize}")
    source = source.replace("\n\\balance\n\\bibliographystyle", "\n\\bibliographystyle")

    portable_lines: list[str] = []
    skipping_fontspec_block = False
    balance_emitted = False

    for line in source.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == r"\usepackage{fontspec}":
            skipping_fontspec_block = True
            continue

        if skipping_fontspec_block:
            if stripped == r"\usepackage{balance}" and not balance_emitted:
                portable_lines.append(line)
                balance_emitted = True
            if stripped.startswith(r"\AtBeginDocument"):
                skipping_fontspec_block = False
                portable_lines.append(line)
            continue

        portable_lines.append(line)

    portable = "".join(portable_lines)
    if r"\usepackage{fontspec}" in portable or r"\setmainfont" in portable:
        raise RuntimeError("portable TeX still contains fontspec directives")
    if r"\input{../../shared/preamble}" in portable:
        raise RuntimeError("portable TeX still depends on a repo-relative preamble")
    if r"\date{\today}" in portable:
        raise RuntimeError("portable TeX still uses a moving date")
    return portable


def main() -> None:
    if SOURCE_DIR.exists():
        shutil.rmtree(SOURCE_DIR)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)

    paper_tex = make_portable_tex(SOURCE_TEX.read_text())
    (SOURCE_DIR / "paper.tex").write_text(paper_tex)
    todo_macro = r"\newcommand{\todo}[1]{\textcolor{red}{TO" + "DO: #1}}" + "\n"
    preamble = SOURCE_PREAMBLE.read_text().replace(todo_macro, "")
    (SOURCE_DIR / "preamble.tex").write_text(preamble)
    shutil.copy2(SOURCE_REFS, SOURCE_DIR / "refs.bib")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(SOURCE_DIR.iterdir()):
            info = zipfile.ZipInfo(file_path.name)
            info.date_time = (2026, 6, 29, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, file_path.read_bytes())

    files = {
        file_path.name: {
            "bytes": file_path.stat().st_size,
            "sha256": sha256(file_path),
        }
        for file_path in sorted(SOURCE_DIR.iterdir())
    }
    manifest = {
        "title": "PolicyStrata: Responsibility-Scoped Testing for Cross-Layer Policy Drift in LLM Data Agents",
        "created_for": "arXiv public preprint source upload",
        "top_level_file": "paper.tex",
        "recommended_processor": "pdflatex",
        "source_directory": str(SOURCE_DIR),
        "zip_path": str(ZIP_PATH),
        "zip_sha256": sha256(ZIP_PATH),
        "files": files,
        "notes": [
            "The upload zip intentionally excludes generated PDFs and auxiliary files.",
            "The bundle rewrites the repo-relative preamble include to a local include.",
            "The bundle removes fontspec/font-name lookups for arXiv portability.",
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
