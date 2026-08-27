# PolicyStrata Submission Ledger

Last updated: 2026-06-29

Use this file as the source of truth before uploading anything. Each submission must record its
artifact checksum after the final PDF or proposal is generated.

| Venue | Product | Deadline | Status | Anonymous | Archival / Proceedings | Submission URL | Artifact SHA256 | Conflict Status |
|---|---|---:|---|---|---|---|---|---|
| SPLASH/ISSTA 2026 Tool Demonstrations | 3-page ACM tool-demo paper + video | 2026-06-26 AoE | Submitted | No | Proceedings-style tool demo | https://splashissta2026-demo.hotcrp.com/paper/38 | `de90c8d2d44cb79cf7751902c105d64d6303f2fa67ed9779a234b626d4b95642` | Frozen; do not resubmit substantially identical text elsewhere while under review |
| ISSRE 2026 Industry Track | 1-2 page tool-demo abstract | 2026-06-28 abstract; 2026-07-05 paper; 2026-08-15 non-proceedings demo | Submitted as EasyChair #406 | No | Industry track; submitted as Enlightening Talk / Tool Demo | https://easychair.org/conferences/?conf=issre2026 | `cd35b40bd9713c95ddade16697c8774bfa82dc7b87a7ad4af39a729be2f77069` | Submitted safely as industry/tool-demo product; do not overwrite packet |
| AI Expo 2026 | Practitioner talk proposal | 2026-07-06 | Submitted via public CFP form; no receipt number surfaced | No | Non-archival talk | https://aiexpo.us/call-for-speakers | N/A | Safe parallel practitioner proposal |
| AgenticDev 2026 | 5-page demo/tool paper | 2026-07-15 | Planned | Yes | ASE workshop proceedings | https://agenticdev2026.hotcrp.com | TBD | Use only if materially distinct from SECUTE or if SECUTE is not submitted |
| SECUTE 2026 | 3-page anonymous ACM tool/data paper + anonymous artifact zip | 2026-07-17 | Paused by author; do not proceed unless explicitly resumed | Yes | ASE workshop proceedings | https://secute2026.hotcrp.com | `d8182fb6d9b6d6a4a8ffec119e53ec6b3d34896bc4c7c24d38fb3ba376e76225` | Public Path A chosen; SECUTE anonymity would be compromised by public preprint promotion |
| arXiv public preprint | Public long paper + public artifact links | No deadline | Ready for manual upload | No | Non-peer-reviewed preprint | https://arxiv.org/submit | `c83fe33345306699d373bce1e4adec3805a772721e65f9f2f31e3158558b2d7c` | Public Path A chosen; do not also submit substantially similar anonymous proceedings paper without rechecking conflicts |
| REALM @ EMNLP 2026 | Non-archival short paper | 2026-07-17 | Planned | Yes | Non-archival preferred; archival goes to ACL Anthology | https://openreview.net | TBD | Use non-archival if SECUTE is active |
| MAS-GAIN 2026 | Backup short/tool paper | 2026-07-10 abstract; 2026-07-17 paper | Backup only | Depends on site policy | ASE workshop proceedings | https://easychair.org/conferences/?conf=masgain2026 | TBD | Do not submit if SECUTE or AgenticDev archival overlap is active |
| TRUST 2026 | Short paper or experience report | 2026-07-23 | Planned backup | Yes | ASE workshop proceedings | https://trust26.hotcrp.com | TBD | Use governance/audit framing; avoid overlapping SECUTE claims |
| RASE 2026 | 4-page demo or 2-page position | 2026-07-24 | Planned backup | Yes | ASE workshop proceedings | https://easychair.org/conferences/?conf=rase2026 | TBD | Use as fallback or position paper, not duplicate SECUTE |
| AISec 2026 | Benchmark/security paper | 2026-07-24 | Hold | Yes | ACM archival workshop | https://aisec26.hotcrp.com | TBD | Hold until stronger adversarial/security evaluation exists |
| POVC 2026 | Presentation or poster | 2026-07-29 | Planned | No for presentation | Papers/posters may be proceedings; presentations can discuss ongoing work | https://promptops2026.hotcrp.com | TBD | Prefer presentation to avoid proceedings conflict |
| DAI 2026 | 8-page research paper | 2026-07-27 abstract; 2026-08-03 paper | Hold | Yes | ACM ICPS proceedings | https://openreview.net | TBD | Hold unless rewritten as a distinct agentic-AI systems paper |

## Ledger Rules

- Do not upload a proceedings paper without first checking this ledger.
- Do not reuse the SPLASH/ISSTA PDF, title block, or abstract as the body of another proceedings submission.
- Every double-blind packet must remove names, affiliations, emails, Raintree branding, GitHub owner identity, public paper URLs, and BetterOff identifying details unless allowed by venue policy.
- Every submitted artifact must have a final SHA256 recorded here.

## Prepared SECUTE Packet

- PDF: `conference-kit/submissions/secute-2026/secute-tool-data-paper.pdf`
- PDF SHA256: `0bed53ac4c697fccd79612e0e03d9a966f0368a605ff4a20df2a69c13ac0d805`
- Anonymous artifact zip:
  `/Users/mb1/Code/raintree/products/policystrata/dist/policystrata-secute-2026-anonymous-artifact.zip`
- Artifact SHA256: `d8182fb6d9b6d6a4a8ffec119e53ec6b3d34896bc4c7c24d38fb3ba376e76225`
- SECUTE source branch: `codex/secute-2026-artifact`
- SECUTE PR for anonymous hosting: `https://github.com/raintree-technology/policystrata/pull/8`
- Remaining blocker: choose artifact-link strategy. Anonymous GitHub is paused by author preference.
  If resumed, use a low-risk GitHub account with no private repos or org access; then replace the
  artifact URL placeholder in the paper, rebuild the PDF, and upload through HotCRP.

## arXiv Plan

- Product: public long paper, not the anonymous SECUTE short paper.
- Current strategy: Path A public preprint first; SECUTE is paused.
- Upload zip:
  `conference-kit/submissions/arxiv-public-preprint/policystrata-arxiv-source.zip`
- Upload zip SHA256:
  `c83fe33345306699d373bce1e4adec3805a772721e65f9f2f31e3158558b2d7c`
- Source bundle contains only `paper.tex`, `preamble.tex`, and `refs.bib`.
- Manual upload fields are recorded in:
  `conference-kit/submissions/arxiv-public-preprint/submission-fields.md`
