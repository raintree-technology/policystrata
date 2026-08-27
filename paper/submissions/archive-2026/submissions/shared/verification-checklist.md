# Submission Verification Checklist

Run this checklist for each venue packet before upload.

## PDF And Text

- No `TODO`, `TBD`, placeholder URL, or stale video URL.
- Page count is within the venue limit.
- References are accurate and not invented.
- Tables render cleanly in the actual PDF, not only in extracted text.
- All result numbers match the latest reproduction output or are phrased as one local run.

## Double-Blind Packets

- No author name, company name, email, Raintree URL, Raintree GitHub owner, BetterOff brand, acknowledgments, or PDF metadata.
- Artifact link is anonymized or omitted with a clear data availability explanation allowed by the venue.
- Self-citations are written in third person where needed.

## Artifact

- Reproduction command is exact.
- Expected output is listed.
- No LLM API key is required for deterministic tests.
- No host `psql` is required; Postgres uses Python or Docker.
- SHA256 is recorded in `conference-kit/submission-ledger.md`.

## Conflict Check

- Confirm whether the venue product is archival/proceedings.
- Confirm whether SPLASH/ISSTA, SECUTE, AgenticDev, TRUST, RASE, REALM archival, AISec, or DAI is already under review.
- If another similar archival product is under review, submit only a non-archival talk/presentation/poster or wait.
