# Security Policy

PolicyStrata is a deterministic policy-regression testing artifact. It is not an authorization
boundary or a replacement for application/database access controls.

## Reporting

Report suspected vulnerabilities privately to `support@raintree.technology`.

Please include the affected version or commit, reproduction steps, and expected impact. Do not send
live customer data, production credentials, or proprietary schemas; use a synthetic reproduction
when possible.

## Scope

Security-relevant issues include:

- imported SQL escaping the read-only allowlist;
- scanner behavior that mutates a configured database;
- credential or secret disclosure in generated artifacts;
- installation or dependency issues that affect normal CLI use.

Detection gaps against unknown production incidents are methodology limitations, not security
vulnerabilities in the artifact.
