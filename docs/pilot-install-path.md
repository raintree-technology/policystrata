# Pilot Install Path

PolicyStrata pilots should use one primary install path per artifact type:

- Python CLI/scanner/runner: `uvx policystrata` or `pipx run policystrata`.
- Node recorder/runtime: `npm install policystrata`.
- Customer-hosted gateway: `npm install @policystrata/agent-trust-gateway`.

Do not introduce a Docker image or signed binary as a pilot install path until a pilot explicitly
chooses that packaging shape. The generic gateway Dockerfile in
[`gateway-deployment-examples.md`](gateway-deployment-examples.md) is a deployment sketch, not a
published PolicyStrata image commitment.

Release docs should keep PyPI and npm as the recommended paths until this decision is revisited.
