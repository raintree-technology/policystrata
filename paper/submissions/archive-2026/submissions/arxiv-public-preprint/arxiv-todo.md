# arXiv Public Preprint Todo

Status: Path A active. Public preprint first; SECUTE/anonymous sharing is paused.

## Decision

Upload the public long PolicyStrata paper to arXiv after source-bundle verification.
Do not edit the already-submitted SPLASH/ISSTA packet, and do not mention any
active double-anonymous venue.

## Package Inputs

- public PDF source: `/Users/mb1/Code/raintree/papers/papers/policystrata/paper.tex`
- shared preamble source: `/Users/mb1/Code/raintree/papers/shared/preamble.tex`
- bibliography: `/Users/mb1/Code/raintree/papers/papers/policystrata/refs.bib`
- package builder: `/Users/mb1/Code/raintree/papers/conference-kit/submissions/arxiv-public-preprint/build_arxiv_package.py`
- generated upload zip: `/Users/mb1/Code/raintree/papers/conference-kit/submissions/arxiv-public-preprint/policystrata-arxiv-source.zip`
- generated manifest: `/Users/mb1/Code/raintree/papers/conference-kit/submissions/arxiv-public-preprint/package-manifest.json`
- generated upload zip SHA256: `c83fe33345306699d373bce1e4adec3805a772721e65f9f2f31e3158558b2d7c`

## Upload Metadata

- title: `PolicyStrata: Responsibility-Scoped Testing for Cross-Layer Policy Drift in LLM Data Agents`
- authors: `Zachary Roth`
- likely primary category: `cs.SE`
- likely cross-list: `cs.CR` only if the submission form accepts it cleanly
- comments: `8 pages. Public artifact and reproducibility kit available at https://github.com/raintree-technology/policystrata.`
- source processor: `pdflatex`

## Checks Before Upload

- Source bundle compiles from its own root.
- No generated PDF or auxiliary files are inside the arXiv source zip.
- No stale SECUTE/anonymous-review language appears in the public paper or metadata.
- Public author/company metadata is intentional.
- Public artifact links resolve.
- Result claims match a fresh artifact run or are explicitly worded as a checked run.
- PDF visually inspected in the arXiv preview before clicking final submit.

## Manual arXiv Steps

1. Sign in at `https://arxiv.org/login`.
2. Start a new submission from `https://arxiv.org/submit`.
3. Upload `policystrata-arxiv-source.zip`.
4. Select `pdflatex` if arXiv asks for the TeX processor.
5. Use the fields in `submission-fields.md`.
6. Review the generated PDF preview visually.
7. Submit only if the preview matches the checked public paper and the metadata is correct.
