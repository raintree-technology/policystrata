# SECUTE 2026 Requirements

Last checked: 2026-06-29

Official page: https://conf.researchr.org/home/ase-2026/secute-2026

Submission site: https://secute2026.hotcrp.com/

## Fit

PolicyStrata fits SECUTE only if framed as software-security testing infrastructure:

- automated generation of security test cases;
- benchmarking security-testing approaches;
- oracle problems in security test cases;
- security testing for non-source artifacts;
- CI/CD integration of security tests;
- empirical evidence from real-world or realistic software-system contexts.

## Paper Type

Use the Tool and Data paper category.

- Maximum length: 5 pages including references.
- Format: ACM Primary Article Template.
- LaTeX class: `\documentclass[sigconf,review,anonymous]{acmart}`.
- Bibliography style: `ACM-Reference-Format`.
- Review: double anonymous.

## Required Content

- Clear threat model.
- Security-testing problem statement.
- Tool workflow and security oracle.
- Test-case generation and witness minimization.
- Evaluation and baselines.
- Data Availability Statement after the last paper section and inside the page limit.
- Limitations and ethics.

## Artifact Requirement

During review, artifacts should be publicly accessible and anonymized. No DOI is required before
acceptance. If accepted, the artifact link must be updated to a DOI-backed archive.

The anonymized artifact must include:

- README with one-command reproduction path.
- Expected outputs.
- Data and scripts used for claims.
- Anonymized fixture data only.
- No Raintree, BetterOff, author, personal email, public preprint, or GitHub owner identifiers.
- Clear justification for any data that cannot be released.

## Conflict Constraint

SECUTE papers must not have been published elsewhere and must not be under review or submitted for
review elsewhere while under SECUTE consideration. Do not submit substantially similar AgenticDev,
MAS-GAIN, TRUST, RASE, AISec, DAI, or archival REALM papers at the same time.

SPLASH/ISSTA and ISSRE are tool/demo products already submitted. The SECUTE paper must be rewritten
with a distinct security-testing framing, anonymous artifact, and page-limited tool/data argument.
