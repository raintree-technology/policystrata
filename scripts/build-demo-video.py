#!/usr/bin/env python3
"""Build a narrated, captioned PolicyStrata walkthrough on macOS."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "paper" / "build" / "PolicyStrata-demo.mp4"
FONT = "/System/Library/Fonts/SFNS.ttf"
MONO_FONT = "/System/Library/Fonts/SFNSMono.ttf"


@dataclass(frozen=True)
class Segment:
    kicker: str
    title: str
    body: tuple[str, ...]
    narration: str
    code: bool = False


SEGMENTS = (
    Segment(
        "POLICYSTRATA · NARRATED WALKTHROUGH",
        "Find the first transition that drifted",
        (
            "Deterministic tests for governed data agents",
            "No LLM key · replayable witnesses · CI-friendly",
            "Synthetic demo and production evidence are labeled separately",
        ),
        (
            "PolicyStrata tests a failure mode in data agents. A policy is copied into several "
            "different representations, and those representations can stop agreeing. The tool "
            "checks each transition in execution order and reports the first contract that failed. "
            "We start with a synthetic case so every value is safe to show, then separate that "
            "demonstration from evidence collected on BetterOff's deployed production revision."
        ),
    ),
    Segment(
        "THE POLICY PIPELINE",
        "Six surfaces, five boundaries",
        (
            "manifest → grammar → validator → compiler → database → release",
            "exposure    intent      authorization     SQL      containment    output",
            "Related representations are not equivalent representations.",
        ),
        (
            "The manifest tells the model what exists. The grammar defines valid intent. The "
            "validator authorizes a typed plan. The compiler lowers that plan to SQL. The database "
            "contains row access, and the release layer decides what can leave the system. A "
            "database can block bad SQL, but that does not erase an earlier compiler error. "
            "PolicyStrata keeps attribution and containment separate."
        ),
    ),
    Segment(
        "RUN THE BUILT-IN CASE",
        "One command produces witnesses",
        (
            "$ uv run policystrata demo --out runs/demo",
            "50 deterministic cases · 50 witnesses · no LLM API key",
            "over_permissive=26",
            "lowering_violation=10",
            "semantic_drift=14",
        ),
        (
            "The built-in demo runs fifty deterministic cases without calling a model. Each case "
            "contains a principal, request, semantic plan, version vector, database state, and "
            "expected release decision. The run emits JSONL traces and minimized witnesses. The "
            "aggregate count is a smoke test. The worked example is where the cross-layer behavior "
            "becomes visible."
        ),
        code=True,
    ),
    Segment(
        "WORKED EXAMPLE",
        "Stale tenant-key lowering",
        (
            "Request: Show escalations by severity for my tenant",
            "Principal: acme_analyst",
            "Versions: manifest=v7 · grammar=v7 · validator=v7",
            "          compiler=v5 · database=v7 · release=v7",
            "Canonical decision: allow",
            "Canonical result: 4     Lowered result: 12",
        ),
        (
            "The model-facing surfaces and validator are on version seven, while the compiler is "
            "still on version five. The principal may ask for escalations in its own tenant. The "
            "canonical interpreter returns four rows. The stale lowering emits a predicate against "
            "legacy tenant id, so the lowered query returns twelve rows on the distinguishing "
            "database state."
        ),
        code=True,
    ),
    Segment(
        "RESPONSIBILITY-SCOPED ATTRIBUTION",
        "Compiler failure, then containment",
        (
            "First violated transition: compiler",
            "Class: lowering_violation",
            "Reason: legacy_tenant_id emitted instead of tenant_id",
            "Containment layer: database",
            "Release decision: blocked",
            "Witness: compiler_uses_old_tenant_key_01.json",
        ),
        (
            "PolicyStrata attributes the fault to the compiler because it is the first surface that "
            "violates its declared responsibility. The database later contains the bad query, and "
            "the release layer blocks output. Those defenses matter, but they do not move the "
            "source of drift downstream. The witness retains the version vector, differing values, "
            "containment outcome, release decision, and bounded reduction."
        ),
        code=True,
    ),
    Segment(
        "INDEPENDENTLY AUTHORED SOURCE CASES",
        "MetricFlow exposes adapter limits",
        (
            "Upstream SHA: 45dce78641bb…",
            "68 upstream-authored expected-SQL cases",
            "0 high-confidence failures · 95 warnings",
            "68 synthetic-role fuzz mutations survived",
            "External source cases; Raintree-authored adapter",
        ),
        (
            "A fresh MetricFlow checkout reproduced sixty-eight checked-in traces byte for byte. "
            "MetricFlow maintainers authored the requests and expected SQL. Raintree authored the "
            "bridge because MetricFlow has no native principal, tenant, or release model. The scan "
            "produced no high-confidence failure, but it did produce ninety-five warnings. "
            "Sixty-eight fuzz mutations survived because the bridge role grants every dimension. "
            "This is adapter evidence, not a MetricFlow security claim or an externally operated study."
        ),
        code=True,
    ),
    Segment(
        "DEPLOYMENT-LINKED PILOT",
        "BetterOff's production revision",
        (
            "Production SHA: 3663f1e475eb…",
            "Vercel: READY · dpl_5MQsJfsc…",
            "Live probes: 33 pass · 0 fail · 3 authenticated skips",
            "Adapter: 33 tools · 6 traces · 4 database checks",
            "PolicyStrata scan: 0 findings · gate pass",
        ),
        (
            "BetterOff is in production. The study binds evidence to its exact deployed Git "
            "revision and Vercel deployment. Thirty-three live HTTP boundary probes passed and "
            "none failed. Three authenticated reads were skipped because no isolated production "
            "smoke principal is configured. On the same deployed revision, the checked-in adapter "
            "covers thirty-three tools, six SQL traces, and four database checks. Its disposable "
            "fixture scan passes with zero findings."
        ),
        code=True,
    ),
    Segment(
        "CLAIM BOUNDARY",
        "What remains",
        (
            "✓ deployed revision and live denial boundaries",
            "✓ two historical missing-RLS revisions reproduced and mapped",
            "✓ one export-audit gap reproduced outside the v1 taxonomy",
            "△ authenticated cross-tenant probes need a smoke principal",
            "△ no customer-operated or independently operated deployment study",
            "Evidence and limits: docs/production-pilot.md",
        ),
        (
            "The new evidence closes the claim that BetterOff is only a synthetic application "
            "fixture. It also replays two historical missing-RLS revisions that map to v1, plus an "
            "export-audit omission that falls outside the taxonomy. What remains is narrower. "
            "Authenticated cross-tenant probes need an isolated production smoke principal, and "
            "no external team has operated the deployment study. The paper preserves those "
            "boundaries along with every command, revision, input hash, and skipped probe."
        ),
    ),
)


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=capture,
        text=True,
    )


def body_svg(segment: Segment) -> str:
    font = MONO_FONT if segment.code else FONT
    size = 28 if segment.code else 30
    y = 390
    lines: list[str] = []
    for raw_line in segment.body:
        for line in textwrap.wrap(raw_line, width=62 if segment.code else 56) or [""]:
            lines.append(
                f'<text x="150" y="{y}" fill="#dce7e2" font-family="{font}" '
                f'font-size="{size}" font-weight="400">{html.escape(line)}</text>'
            )
            y += 46
        y += 10
    return "".join(lines)


def slide_svg(segment: Segment, index: int) -> str:
    kicker = html.escape(segment.kicker)
    title = html.escape(segment.title)
    counter = f"{index + 1:02d}/{len(SEGMENTS):02d}"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
<rect width="1920" height="1080" fill="#07110e"/>
<rect x="72" y="72" width="1776" height="936" rx="34" fill="#0c1c17" stroke="#275d4c" stroke-width="2"/>
<circle cx="150" cy="145" r="18" fill="#78d6ac"/>
<text x="190" y="160" fill="#78d6ac" font-family="{FONT}" font-size="28"
 font-weight="600">{kicker}</text>
<text x="150" y="285" fill="#f2f7f5" font-family="{FONT}" font-size="52"
 font-weight="700">{title}</text>
{body_svg(segment)}
<text x="150" y="948" fill="#7e9d91" font-family="{FONT}" font-size="25">
PolicyStrata · responsibility-scoped policy-drift testing</text>
<text x="1745" y="948" fill="#7e9d91" font-family="{FONT}" font-size="25">{counter}</text>
</svg>"""


def render_png(svg_path: Path, output_dir: Path) -> Path:
    rendered = output_dir / f"{svg_path.stem}.png"
    run(["sips", "-s", "format", "png", str(svg_path), "--out", str(rendered)])
    if not rendered.exists():
        raise RuntimeError(f"sips did not render {svg_path}")
    return rendered


def duration(path: Path) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture=True,
    )
    return float(result.stdout.strip())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def build_video(out_path: Path, voice: str, rate: int) -> None:
    scratch = ROOT / "tmp" / "demo-video"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    videos: list[Path] = []
    captions: list[str] = []
    cursor = 0.0
    for index, segment in enumerate(SEGMENTS):
        stem = f"segment-{index + 1:02d}"
        svg = scratch / f"{stem}.svg"
        svg.write_text(slide_svg(segment, index), encoding="utf-8")
        png = render_png(svg, scratch)
        audio = scratch / f"{stem}.aiff"
        run(["say", "-v", voice, "-r", str(rate), "-o", str(audio), segment.narration])
        segment_duration = duration(audio) + 1.0
        video = scratch / f"{stem}.mp4"
        run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-loop", "1", "-framerate", "30", "-i", str(png), "-i", str(audio),
                "-t", f"{segment_duration:.3f}", "-vf", "scale=1920:1080",
                "-c:v", "libx264", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                "-movflags", "+faststart", str(video),
            ]
        )
        videos.append(video)
        captions.append(
            f"{index + 1}\n{timestamp(cursor)} --> {timestamp(cursor + segment_duration)}\n"
            f"{segment.narration}\n"
        )
        cursor += segment_duration

    concat = scratch / "concat.txt"
    concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in videos), encoding="utf-8")
    joined = scratch / "joined.mp4"
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
            "-safe", "0", "-i", str(concat), "-c", "copy", str(joined),
        ]
    )
    subtitles = scratch / "PolicyStrata-demo.en.srt"
    subtitles.write_text("\n".join(captions), encoding="utf-8")
    webvtt = out_path.with_name(f"{out_path.stem}.en.vtt")
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(subtitles), str(webvtt),
        ]
    )
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(joined),
            "-i", str(subtitles), "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0",
            "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
            "-metadata:s:s:0", "language=eng",
            "-metadata", "title=PolicyStrata narrated walkthrough",
            "-movflags", "+faststart", str(out_path),
        ]
    )
    metadata = {
        "schema_version": 1,
        "output": str(out_path.relative_to(ROOT)),
        "duration_seconds": round(duration(out_path), 3),
        "segments": len(SEGMENTS),
        "voice": voice,
        "rate": rate,
        "captions": "embedded mov_text, language=eng",
        "webvtt": str(webvtt.relative_to(ROOT)),
        "sha256": sha256(out_path),
    }
    out_path.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--voice", default="Samantha")
    parser.add_argument("--rate", type=int, default=175)
    args = parser.parse_args()
    build_video(args.out.resolve(), args.voice, args.rate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
