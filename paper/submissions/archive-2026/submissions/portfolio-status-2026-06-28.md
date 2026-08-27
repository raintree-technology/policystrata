# PolicyStrata Submission Portfolio Status

Created: 2026-06-28
Last updated: 2026-06-29

## Frozen Submission

The SPLASH/ISSTA 2026 Tool Demonstrations packet is frozen under
`conference-kit/submitted/splash-issta-2026-tool-demo/`.

- Submitted HotCRP record: https://splashissta2026-demo.hotcrp.com/paper/38
- Submitted PDF SHA256: `de90c8d2d44cb79cf7751902c105d64d6303f2fa67ed9779a234b626d4b95642`
- YouTube demo: https://www.youtube.com/watch?v=skQQajjI7-0
- Demo video SHA256: `ae9a7a9b4e9ff2e886c34ec2ea1dfad76d928f6fbbbc366ee8079b58cf4c86f5`

Do not edit or overwrite these files. Future submissions must be built from separate venue folders.

## Submitted

- ISSRE 2026 Industry Track: submitted through EasyChair as Submission 406.
- Portal status text: `The submission has been saved!`
- Portal submitted timestamp: `Jun 29, 00:57`.
- Submitted product: Enlightening Talk / Tool Demo.
- Submitted PDF:
  `conference-kit/submissions/issre-2026-industry/issre-industry-tool-demo-abstract.pdf`.
- ISSRE PDF SHA256:
  `cd35b40bd9713c95ddade16697c8774bfa82dc7b87a7ad4af39a729be2f77069`.
- AI Expo 2026: submitted through the public call-for-speakers form on 2026-06-28 PDT.
- AI Expo receipt note:
  `conference-kit/submissions/ai-expo-2026/submission-receipt.md`.

## Ready Locally

- SECUTE 2026: anonymous ACM tool/data paper and anonymous artifact zip prepared locally under
  `conference-kit/submissions/secute-2026/`.
  - PDF: `conference-kit/submissions/secute-2026/secute-tool-data-paper.pdf`
  - PDF SHA256: `0bed53ac4c697fccd79612e0e03d9a966f0368a605ff4a20df2a69c13ac0d805`
  - Artifact zip:
    `/Users/mb1/Code/raintree/products/policystrata/dist/policystrata-secute-2026-anonymous-artifact.zip`
  - Artifact SHA256: `d8182fb6d9b6d6a4a8ffec119e53ec6b3d34896bc4c7c24d38fb3ba376e76225`
  - Source branch pushed: `codex/secute-2026-artifact`
  - PR for anonymous hosting: `https://github.com/raintree-technology/policystrata/pull/8`
  - Anonymous GitHub path: paused by author preference because OAuth requests broad repository
    access.
  - Temporary public mirror for later anonymization:
    `https://github.com/zacharyr0th/secute-2026-review-artifact`
  - Status: paused by author preference while Path A public preprint proceeds.
  - Remaining blocker if resumed: choose artifact-link strategy, insert final artifact URL or
    supplementary artifact note in paper, rebuild PDF, submit.
- arXiv public preprint: ready for manual upload under
  `conference-kit/submissions/arxiv-public-preprint/`.
  - Upload zip:
    `conference-kit/submissions/arxiv-public-preprint/policystrata-arxiv-source.zip`
  - Upload zip SHA256:
    `c83fe33345306699d373bce1e4adec3805a772721e65f9f2f31e3158558b2d7c`
  - Clean-root compile: 8-page PDF, warnings only.
  - Public Path A is active; SECUTE is paused.
- Backup/non-conflicting venue plans drafted for AgenticDev, REALM, MAS-GAIN, TRUST, RASE,
  AISec, POVC, and DAI.

## Verification Performed

PolicyStrata package checks from `/Users/mb1/Code/raintree/products/policystrata`:

```text
uv run ruff check .  -> pass
uv run mypy src      -> pass
uv run pytest        -> 127 passed, 5 optional integration tests skipped
```

Fresh SECUTE anonymous artifact unpack checks:

```text
uv run --extra dev ruff check . -> pass
uv run --extra dev mypy src     -> pass
uv run --extra dev pytest       -> 100 passed, 5 optional integration tests skipped
SECUTE scan fixture             -> expected gate fail, 5 high-confidence findings
```

Fresh deterministic reproduction run:

```text
POLICYSTRATA_RUN_ROOT=/tmp/policystrata-portfolio-final ./scripts/reproduce-final.sh
```

Observed output:

```text
1720/1720 non-clean injected cases killed
80 clean controls, 0 false positives
1800 traces total
1720 minimized witnesses
median witness size: 3302 bytes
run directory: 1760 files, 17 MB
fresh local wall-clock runtime: 3.99s
```

PDF checks:

- Long paper rebuilt to `dist/PolicyStrata.pdf`.
- Long paper page count: 8.
- ISSRE abstract page count: 1.
- Sampled rendered pages for the long paper and ISSRE abstract; no obvious table overflow or
  corrupted first-page flow in the sampled renders.
- Frozen SPLASH/ISSTA archive checksums pass with `shasum -a 256 -c checksums.sha256`.

## Still Requires Portal Action

- AI Expo did not show a persistent receipt number or confirmation page. Do not resubmit unless the
  organizer says no proposal was received.
- arXiv public preprint still requires manual upload through arXiv.
- Do not submit SECUTE, AgenticDev, MAS-GAIN, TRUST, RASE, AISec, DAI, or archival REALM in parallel
  with substantially similar proceedings text. SECUTE is paused while public Path A proceeds.

## Live Venue Constraints Rechecked

- ISSRE Industry Track permits a 1-2 page tool-demo abstract, requires non-anonymous IEEE-style PDF,
  and lists June 28, 2026 for abstract submission.
- SECUTE 2026 lists tool/data papers up to 5 pages including references, double-anonymous review,
  a required data availability statement, anonymized public artifacts during review, and no
  simultaneous substantially similar submissions.
- ASE double-anonymous guidance says authors are encouraged to use titles different from arXiv or
  similar preprints and should not publicly use the submission title during review.
- arXiv submissions should be topical, refereeable scientific contributions that follow accepted
  scholarly standards.
- REALM 2026 explicitly permits non-archival submissions to overlap with work under review elsewhere;
  archival submissions remain anonymous and exclusive during review.
- AI Expo 2026 lists July 6, 2026 as the speaker proposal deadline.
