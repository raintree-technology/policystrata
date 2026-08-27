# Today Submission Checklist

Date: 2026-06-26

## Decisions To Make First

- Pick exactly one active archival venue for the current paper version.
- Decide whether the current manuscript is a research paper, practitioner experience paper, or
  security paper. Do not blur these.
- If submitting to a double-blind archival venue, use the anonymous paper and anonymous artifact path.
- If submitting to practitioner events, use the problem-first talk proposal and public identity.

## Submit Or Prepare Today

### 1. ICSE 2027 Research

Go/no-go:
- Go only if the mandatory abstract was registered by 2026-06-23.
- If no abstract was registered, do not spend today on ICSE Research. Move to FSE 2027 or ICSE SEIP.

Today actions if go:
- Convert to ICSE format.
- Verify anonymization with `pdftotext paper-anon.pdf - | rg "<identity strings>"`.
- Add or verify open-science/artifact instructions.
- Check references for hallucinated or unverifiable entries.
- Confirm the artifact link is anonymous.
- Submit by 2026-06-30.

### 2. FSE 2027 Research

Go/no-go:
- Best default archival lane if ICSE Research registration was missed.
- Deadline is 2026-10-02, so today is for registration prep, not panic submission.

Today actions:
- Create `fse-2027/` copy of the paper source.
- Keep current contribution shape: method, benchmark, baselines, limitations, artifact.
- Add a Data Availability section after conclusion.
- Make `conference-kit/` the replication package draft.
- Build a blinded artifact package plan: anonymous repo now, DOI after acceptance.
- Open an issue list for missing FSE-level evidence:
  - larger benchmark slice;
  - one extra domain or stress-test axis;
  - clearer baseline rationale;
  - artifact README split into smoke/full runs.

### 3. ICSE 2027 SEIP

Go/no-go:
- Good if you can tell a practical story and show systematic lessons.
- Submission deadline is 2026-10-23.
- Not double-blind.

Today actions:
- Create a separate SEIP outline, not just a retitled research paper.
- Add sections:
  - Practical problem;
  - Context and constraints;
  - Investigation method;
  - What failed across layers;
  - Lessons and best practices;
  - Artifact and reproducibility;
  - Limitations.
- Remove heavy formulas from main text.
- Use one strong tenant/purpose/release failure example.

### 4. NDSS 2027 Fall

Go/no-go:
- Not ready as-is.
- Go only if you can add a security threat model and adversarial evaluation before 2026-08-19.

Today actions:
- Draft a threat model:
  - attacker capability;
  - target assets;
  - policy surface;
  - database/RLS role;
  - release channel;
  - assumptions and non-goals.
- Add at least three adversarial case studies.
- Add security baselines or comparisons.
- Add ethics statement.
- Decide by 2026-07-05 whether to pursue or drop.

### 5. USENIX Security 2027 Cycle 1

Go/no-go:
- Same as NDSS: not ready without a real security paper.
- Registration is due 2026-08-18; submission is due 2026-08-25.

Today actions:
- Reuse the NDSS threat model draft.
- Add Open Science and Ethical Considerations appendices.
- Verify all artifacts are review-accessible and anonymous.
- Decide by 2026-07-10 whether the security version is credible.

### 6. Monktoberfest

Go/no-go:
- Good to submit today.
- CFP is open and early submission is encouraged.

Today actions:
- Use the title: `When Policy Crosses Layers: Testing Trust in LLM Data Agents`.
- Use the social + technical proposal in `venue-proposal-variants.md`.
- Keep it story-first:
  - a user asks a normal data question;
  - every layer looks plausible;
  - the release is wrong;
  - the witness shows where responsibility broke.
- Avoid paper/benchmark jargon in the abstract.

### 7. QCon

Go/no-go:
- Worth a spontaneous submission or warm intro today.
- Not a standard CFP.

Today actions:
- Use the title: `Policy Tests for Data Agents With Real Blast Radius`.
- Pitch it as a production-pattern talk, not a research paper.
- Include:
  - operational problem;
  - architecture layers;
  - failure examples;
  - guardrail/test pattern;
  - what teams can adopt Monday.

### 8. PyCon, AI Engineer, Open Source GenAI/ML

Go/no-go:
- Current checked CFPs are closed.
- Prepare next-cycle assets today.

Today actions:
- Save three proposal variants:
  - Python open-source demo;
  - AI engineer demo;
  - open-source GenAI/ML workshop.
- Create a 5-minute demo script:
  - run seeded suite;
  - inspect witness;
  - show first violated transition;
  - export trace.

### 9. FAccT, AIES, NeurIPS E&D, ICLR

Go/no-go:
- Current checked deadlines are closed.
- Prepare next-cycle adaptations.

Today actions:
- FAccT/AIES: add ethics, adverse impacts, and institutional governance framing.
- NeurIPS E&D: add benchmark card/evaluation card and make DataPolicyDriftBench central.
- ICLR workshop: add reproducibility and ethics statements, shift to ML-eval language.

## Artifact Package Work Completed Today

- Added `README.md` at the root of `conference-kit/`.
- Added a 30-minute smoke test path to `artifact-reviewer-guide.md`.
- Added SHA256 checksums for both PDFs.
- Added expected runtime guidance from the verified local run.
- Added `figures/pipeline-diagram.md` as the source for the pipeline diagram.
- Added `STATUS`, `REQUIREMENTS`, `INSTALL`, and `LICENSE` files for artifact-review packaging.
- Added scanner/doctor audit coverage language for privacy and terms documents, prompt manifests, source
  maps, release tests, remediation todos, and CI gates.

## Remaining Package Work

- Export a polished PDF/PNG/SVG version of the pipeline diagram for the paper and talk deck.
- Create an anonymous artifact archive or anonymous repository link before any double-blind
  submission.
- Create a DOI-backed public artifact archive after acceptance or for non-anonymous venues.

## Hard Stop Checks

- No concurrent archival duplicate submission.
- No identity strings in anonymous PDF or artifact.
- No product-first title.
- No unsupported production recall claim.
- No "grammar membership is security" implication.
- No artifact command requiring an LLM API key.
- No host `psql` dependency.
