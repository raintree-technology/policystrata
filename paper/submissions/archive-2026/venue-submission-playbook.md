# PolicyStrata Venue Submission Playbook

Checked on: 2026-06-26

This playbook separates what can be submitted now from what should be prepared for the next cycle.
Do not submit the same, or substantially similar, archival paper to multiple peer-reviewed venues at
the same time. Practitioner talks can usually be submitted in parallel unless the event says
otherwise.

## Recommended Order

1. FSE 2027 Research, if aiming for the strongest software-engineering archival lane.
2. ICSE 2027 SEIP, if reframing around practitioner lessons, packaging, and systematic use.
3. NDSS 2027 Fall or USENIX Security 2027 Cycle 1 only after adding a real security threat model and
   adversarial evaluation.
4. Monktoberfest and QCon-style practitioner pitches today, because those reward a concrete story and
   do not require the paper to be finished.
5. PyCon, AI Engineer, Open Source GenAI/ML, NeurIPS E&D, ICLR, FAccT, and AIES should be prepared
   for next cycle unless a current subtrack opens.

## Cross-Venue Rules

- Keep the claim boundary: 1720/1720 is deterministic artifact-suite coverage over implemented
  non-equivalent operators and fixtures, with 80 clean controls and 0 false positives. It is not
  production recall and not an authorization boundary.
- Use one narrow phrase consistently: "cross-layer policy drift testing for LLM data agents."
- Keep constrained generation positioned as reliability, not security.
- For double-blind venues, use `paper-anon.pdf`, remove identity strings from text, PDF
  metadata, artifact links, repository names, acknowledgements, and figures.
- For artifact links, use an anonymous repository or supplemental upload during review. Use Zenodo or
  another DOI-backed archive only when de-anonymization is allowed or after acceptance.
- Put reproducibility in the main paper, not only in the appendix: exact commands, seeds, expected
  outputs, and runtime.
- Add a clear data/artifact availability statement in any SE venue submission.
- Maintain a single source of truth for evidence: `reproduce-final.sh`, `expected-results.md`, and
  the generated `runs/final/evidence.md`.

## Software Engineering Venues

### ISSTA

Status on 2026-06-26: 2026 research submission is closed. Artifact evaluation is relevant only for
accepted ISSTA papers.

Official signals:
- Research papers cover software testing and analysis, including LLM/agent testing, mutation testing,
  regression testing, and analysis/testing for AI.
- ISSTA 2026 required an anonymous artifact link or an explanation, plus a Data Availability section.
- ISSTA artifact evaluation asks for a container or VM, a 30-minute getting-started path, step-by-step
  reproduction instructions, requirements, status, and license files.

Best PolicyStrata fit:
- Research or experience paper under testing and analysis for AI/agentic systems.
- Emphasize mutation testing, regression testing, first-violated-transition witnesses, and
  verifiability.

Required adaptation:
- Add `Data Availability` before references.
- Package a Docker/Podman path or justify the `uv` path plus optional Docker fixture.
- Split reviewer path into "30-minute smoke test" and "full deterministic suite."

Source:
- https://conf.researchr.org/track/issta-2026/issta-2026-research-papers
- https://conf.researchr.org/track/issta-2026/issta-2026-artifact-evaluation

### ICSE Research

Status on 2026-06-26: ICSE 2027 full paper deadline is 2026-06-30, but the mandatory abstract
deadline was 2026-06-23. Submit only if a valid abstract registration already exists.

Official signals:
- Double-anonymous review.
- Authors are encouraged to upload paper info early for conflict handling.
- Open science policy asks authors to make anonymized/curated artifacts available, or explain why
  not.
- Confirmed hallucinated or fabricated references can trigger desk rejection.

Best PolicyStrata fit:
- Research track if the paper is sold as a method plus benchmark and rigorous evaluation.
- Strongest if the paper foregrounds software engineering: representations, contracts, mutation
  operators, baselines, traces, reproducibility.

Required adaptation:
- Verify every citation.
- Add explicit open-science instructions in the paper.
- Keep public website/PyPI references out of the anonymous manuscript unless cited in third person and
  safe for anonymity.

Source:
- https://conf.researchr.org/track/icse-2027/icse-2027-research-track

### ICSE SEIP

Status on 2026-06-26: open for 2026-10-23 submission.

Official signals:
- SEIP is not double-anonymous.
- Papers should address industrially relevant problems through systematic investigation.
- Review criteria are relevance to industrial practice, significance, and presentation quality.
- Main text limit is 10 pages plus 2 reference pages.

Best PolicyStrata fit:
- Use only if the paper is reframed as a practitioner-facing systematic investigation: why governed
  LLM data agents fail across layers, what traces/witnesses helped, and what best practices emerge.
- Less ideal if it remains a mostly formal research-method paper.

Required adaptation:
- Add "context of use" and "lessons learned" sections.
- Replace generic benchmark emphasis with concrete workflows and reviewer-friendly examples.
- Use public author/product identity, but keep brand secondary to the problem.

Source:
- https://conf.researchr.org/track/icse-2027/icse-2027-seip

### ASE

Status on 2026-06-26: ASE 2026 research submission is closed; next cycle should use the same pattern.

Official signals:
- Technical papers are judged on significance, novelty, and soundness.
- Experience papers are judged on importance/scope, insights/evidence, and perspective.
- Verifiability applies to both.
- ASE 2026 required an anonymous artifact link or explanation.
- Artifact review asks for a 30-minute getting-started guide and step-by-step claim reproduction.

Best PolicyStrata fit:
- Strong, especially if positioned as automated support for policy regression testing.
- Use the "Testing and Analysis" and "AI and Software Engineering" areas.

Required adaptation:
- Make "automation" central: generate mutants, run suites, minimize witnesses, export adapters.
- Keep the formulas mostly in the appendix.
- Put expected output examples directly in the artifact guide.

Source:
- https://conf.researchr.org/track/ase-2026/ase-2026-research-track
- https://conf.researchr.org/track/ase-2026/ase-2026-artifact-evaluation

### FSE

Status on 2026-06-26: FSE 2027 research deadline is 2026-10-02.

Official signals:
- FSE 2027 topics include software engineering for ML/AI, software security, software testing, tools,
  program analysis, and reliability.
- Open science policy asks for an anonymized and curated replication package or a reason for not
  providing one.
- FSE 2026 artifact guidance required a DOI-backed persistent repository, README, REQUIREMENTS,
  STATUS, LICENSE, INSTALL, and a copy of the accepted paper.

Best PolicyStrata fit:
- Very strong. This is probably the cleanest archival target.
- Lead with conformance contracts, deterministic benchmark design, baseline comparisons, and artifact
  reproducibility.

Required adaptation:
- Add a Data Availability section after the conclusion.
- Prepare Zenodo DOI after acceptance or when anonymity is no longer required.
- Keep a clean anonymized replication package ready before submission.

Source:
- https://conf.researchr.org/track/fse-2027/fse-2027-papers
- https://conf.researchr.org/track/fse-2026/fse-2026-artifacts

## Governance And Accountability Venues

### FAccT

Status on 2026-06-26: FAccT 2026 submission is closed. Prepare for the next cycle when posted.

Official signals:
- Scope includes evaluations, audits, risk identification, system development/deployment, responsible
  data engineering, risks/failures, and governance.
- 2026 paper limit was 14 pages excluding references, with one extra page for ethics/adverse impact
  statements.
- Submissions must be anonymized and identifying information removed.
- Work without deep engagement with social components can be considered out of scope.

Best PolicyStrata fit:
- Possible, but only after adding sociotechnical framing: institutional data access, auditability,
  governance obligations, release policy, and operational accountability.
- Do not submit a pure testing-method paper here.

Required adaptation:
- Add a governance problem statement and institutional risk scenario.
- Add adverse impacts and limitations.
- Discuss how witnesses support audit and accountability, not just debugging.

Source:
- https://facctconference.org/2026/cfp.html
- https://facctconference.org/2026/authorguide.html

### AIES

Status on 2026-06-26: AIES 2026 submission is closed.

Official signals:
- 2026 submissions used AAAI two-column format, 10 pages including figures/tables, unlimited
  non-discursive references.
- Review was doubly anonymized.
- Optional ethics, positionality, and adverse-impact statements could use one extra page.
- AIES prohibited LLM-generated paper text unless the generated text was part of experimental
  analysis.

Best PolicyStrata fit:
- Possible if framed around AI ethics for governed data agents and policy release.
- Weaker than FAccT unless the paper says more about human/institutional consequences.

Required adaptation:
- Add one-page ethics/adverse-impact statement.
- Use a substantially hand-authored proposal and avoid AI-generated-sounding CFP prose.
- Make the benchmark a tool for accountability evaluation, not just an engineering artifact.

Source:
- https://www.aies-conference.com/2026/call-for-papers/
- https://aaai.org/conference/aaai/aaai-26/reproducibility-checklist/

## Security Venues

### USENIX Security

Status on 2026-06-26: USENIX Security 2027 Cycle 1 registration is due 2026-08-18; submission is due
2026-08-25.

Official signals:
- USENIX Security is a systems security venue.
- Papers without a clear systems security or privacy application may be out of scope.
- Recent policy requires ethics and open-science appendices.
- For 2026, artifacts had to be available during review, anonymous where linked, and explained if not
  shareable.
- ML-focused papers need a clear threat model: attacker, surfaces, generality, and practicality.

Best PolicyStrata fit:
- Not ready as-is. It reads like testing infrastructure, not security research.
- Viable only with an explicit adversary, exploit path, policy bypass surface, and stronger empirical
  security evaluation.

Required adaptation:
- Add a threat model: malicious or confused principal, request construction capability, policy
  version drift, release channel, and database/RLS containment.
- Add adversarial case studies and compare to existing security testing/authorization testing tools.
- Include ethics and open-science appendices.

Source:
- https://www.usenix.org/conference/usenixsecurity27
- https://www.usenix.org/conference/usenixsecurity26/call-for-papers

### NDSS

Status on 2026-06-26: NDSS 2027 summer cycle is closed; fall paper deadline is 2026-08-19.

Official signals:
- NDSS focuses on network and distributed system security, with topic filtering for questionable fit.
- Papers with contributions primarily in another field, such as AI/ML, can be topic-concern desk
  rejected.
- Papers must be double-blind.
- Accepted papers are strongly encouraged to open-source artifacts and submit artifact evaluation.

Best PolicyStrata fit:
- Only if recast as security testing for distributed data-agent systems with a real attack model.
- Better as a future target after a hardened security evaluation.

Required adaptation:
- Show concrete security/privacy contribution, not just authorization hygiene.
- Add adversarial tests, responsible disclosure/ethics discussion if using real systems, and stronger
  baselines from security testing.

Source:
- https://www.ndss-symposium.org/ndss2027/submissions/call-for-papers/
- https://www.ndss-symposium.org/ndss2027/submissions/call-for-artifacts/

### CCS

Status on 2026-06-26: CCS 2026 Cycle B is past submission; use as a policy model for next cycle.

Official signals:
- Requires Open Science appendix.
- Online artifact URL must be anonymous and supplied by the submission deadline.
- Potential ethical concerns require an Ethical Considerations appendix.
- Main content is 12 pages before bibliography and required appendices.

Best PolicyStrata fit:
- Similar to USENIX/NDSS: not the first target unless the work becomes a security paper.

Required adaptation:
- Add anonymous artifact hosting before submission.
- Add security threat model and ethics appendix.
- Be prepared for a higher bar on adversarial novelty.

Source:
- https://www.sigsac.org/ccs/CCS2026/call-for/call-for-papers.html

## ML Evaluation Venues

### NeurIPS Evaluations And Datasets

Status on 2026-06-26: NeurIPS 2026 E&D deadline has passed. Prepare for next cycle.

Official signals:
- The E&D track now treats evaluation as a scientific object of study.
- Scope includes tools, frameworks, benchmark design, stress-testing, audits, and negative results.
- Code is required at submission if the primary contribution is a reusable executable artifact.
- Datasets and code must be hosted, accessible, documented, and anonymized as needed.
- Non-compliance can justify desk rejection.

Best PolicyStrata fit:
- Strong if DataPolicyDriftBench becomes the center: benchmark scope, assumptions, documentation,
  limitations, and evaluative claims.
- Weaker if the paper is mostly a software-engineering method.

Required adaptation:
- Expand DataPolicyDriftBench documentation.
- Add benchmark cards/evaluation cards.
- Make code and data final-form, anonymized, documented, and executable at submission.

Source:
- https://neurips.cc/Conferences/2026/CallForEvaluationsDatasets
- https://neurips.cc/Conferences/2026/EvaluationsDatasetsReviewerGuidelines
- https://neurips.cc/public/guides/PaperChecklist
- https://neurips.cc/public/guides/CodeSubmissionPolicy

### ICLR

Status on 2026-06-26: ICLR 2026 is closed; prepare for next cycle or relevant workshops.

Official signals:
- Double blind; identity-revealing submissions or supplement can be desk rejected.
- Code can be uploaded as supplementary material and is encouraged for replicability.
- Ethics and reproducibility statements are recommended before references.
- Accepted and rejected submissions become de-anonymized after notification.

Best PolicyStrata fit:
- Better as a workshop submission unless the benchmark is expanded and ML evaluation framing becomes
  central.

Required adaptation:
- Add a paragraph-long reproducibility statement.
- Add optional ethics statement.
- Use ML-evaluation language: assumptions, metrics, baselines, benchmark saturation/failure modes.

Source:
- https://iclr.cc/Conferences/2026/AuthorGuide

## Practitioner Venues

### PyCon

Status on 2026-06-26: PyCon US 2026 CFP is closed. Prepare next-cycle talk/poster.

Official signals:
- CFPs are reviewed anonymously in the first round.
- Proposal limit was three per person.
- Talks are usually 30 minutes, with limited 45-minute slots.
- 2026 added AI and Security tracks.
- Reviewers want intended audience, concrete takeaways, detailed outline, links, and non-infomercial
  proposals.
- Proposals written solely or largely by an LLM are rejected.

Best PolicyStrata fit:
- "Testing Policy Drift in Python LLM Data Agents" for AI or Security track.
- Include a live Python CLI demo and a tenant-isolation failure example.

Required adaptation:
- Remove product framing.
- Include audience level, concrete takeaways, and a timed outline.
- Use open-source Python artifact proof, not paper novelty.

Source:
- https://us.pycon.org/2026/speaking/guidelines/
- https://us.pycon.org/2026/speaking/talks/

### AI Engineer

Status on 2026-06-26: AI Engineer World's Fair 2026 speaker submissions are closed.

Official signals:
- The event asks for engineers who ship, not generic AI theory.
- The Sessionize guidance says generic AI-conference talks have near-zero chance.

Best PolicyStrata fit:
- Demo-first talk for builders of agents, evals, and data platforms.

Required adaptation:
- Use a concrete failure narrative and CLI demo.
- Show how to add PolicyStrata to CI for a small agent stack.
- Avoid "introducing PolicyStrata" as the title.

Source:
- https://www.ai.engineer/worldsfair
- https://sessionize.com/aiewf2026/

### Open Source GenAI / ML

Status on 2026-06-26: the checked Linux Foundation AI_dev CFP page is closed/past; monitor next AI
events.

Official signals:
- Relevant topics included AI agents, AI code generation/devtools, data management, eval frameworks,
  LLMOps, responsible AI, and cloud-native AI.
- Session types included lightning talk, 30-minute conference session, panel, and workshop.

Best PolicyStrata fit:
- Open-source tool demo or workshop.

Required adaptation:
- Lead with how open-source agent teams can reproduce policy failures without API keys.
- Show install, run, inspect witness, export traces.

Source:
- https://events.linuxfoundation.org/ai-dev-europe/program/cfp/

### QCon

Status on 2026-06-26: no formal CFP found for QCon SF 2026; QCon says it usually invites speakers but
has a spontaneous submission form.

Official signals:
- QCon wants senior practitioners sharing what is working in production.
- It emphasizes real production patterns, honest lessons, and no hidden product pitches.
- The 2026 SF theme explicitly includes architecting agents, evals, guardrails, observability, and
  resilience.

Best PolicyStrata fit:
- A production-pattern talk: "Policy Tests for Data Agents With Real Blast Radius."

Required adaptation:
- Include operational lessons, failure modes, tradeoffs, and guardrail architecture.
- Do not pitch a library.
- Use one detailed end-to-end story and end with patterns teams can adopt.

Source:
- https://qconsf.com/
- https://qconsf.com/faq/nov2024

### Monktoberfest

Status on 2026-06-26: CFP is open with no hard deadline stated; early submission is encouraged.

Official signals:
- Single-track conference.
- Wants an engaging and insightful story.
- Submissions should touch both social and technology themes.

Best PolicyStrata fit:
- Strong for a narrative talk about how trust moves between people, policies, and software layers.

Required adaptation:
- Less benchmark detail, more story.
- Connect technical policy drift to organizational responsibility and review culture.

Source:
- https://monktoberfest.com/attend/cfp/
