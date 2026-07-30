# PolicyStrata Paper

This directory is the source of truth for the editable PolicyStrata paper.
The website repository contains only the published PDF and rendered page previews.

## Files

- `main.tex`: manuscript
- `preamble.tex`: formatting and paper macros
- `sections/`: one source file per paper section
- `references.bib`: bibliography
- `build/PolicyStrata.pdf`: generated PDF, ignored by Git
- `build/tectonic.log`: full build diagnostics, ignored by Git

## Build

Install Tectonic and qpdf, or make their executables available through `TECTONIC` and `QPDF`, then
run:

```bash
bun run paper:build
```

Use the stricter check before publishing:

```bash
bun run paper:check
```

The build resolves the bibliography, normalizes searchable PDF metadata, verifies the PDF
structure, and writes `paper/build/PolicyStrata.pdf`. Builds use `SOURCE_DATE_EPOCH` when provided
and otherwise use the paper's latest Git commit time, which keeps committed-source builds stable.
The strict check also rejects unresolved citations, missing characters, horizontal overflow, and
source placeholders. Full TeX diagnostics stay in `paper/build/tectonic.log`.

## Publish To The Website

From the sibling `raintree/websites` checkout:

```bash
bun run paper:sync
bun run paper:check
```

The sync command copies the built PDF, regenerates the page-preview PNGs at 150 DPI, removes stale
preview pages, and updates the website's declared page count and SHA-256. It stages replacements
before changing published files. The website check renders the canonical paper again and reports
any PDF, preview, page-count, or hash drift without changing files.

## Editing

Edit the matching file under `sections/`. Keep title, author, date, abstract, and PDF metadata in
`main.tex`; keep layout changes in `preamble.tex`; keep citation records in `references.bib`.
Run `bun run paper:build` for normal drafting and `bun run paper:check` before syncing the website.

## Editing Rules

- Keep benchmark measurements tied to checked-in artifact evidence.
- Keep deterministic fault-model coverage separate from claims about production recall.
- Do not describe the benchmark, scanner, runtime evaluator, or gateway as a replacement for
  application authorization or database controls.
