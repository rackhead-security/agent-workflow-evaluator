# Agent Workflow Evaluator

Agent Workflow Evaluator is an early-stage, deterministic, local-first tool for reviewing the **declared** security properties of AI-agent workflows.

The current implementation is **Slice 1 only**: package foundation, safe YAML parsing, typed schema models, normalized validation errors, and fail-closed validation. It does not yet evaluate `RH-AWE-001` through `RH-AWE-008` or generate security reports.

The approved implementation contract is [`docs/v0.1-spec.md`](docs/v0.1-spec.md). The older [`docs/schema.md`](docs/schema.md) is deprecated historical context.

## Current capabilities

- Parse bounded UTF-8 YAML with a strict loader derived from PyYAML `SafeLoader`.
- Reject YAML aliases, duplicate mapping keys, and inputs larger than 1 MiB.
- Reject unknown fields and unsupported schema or policy versions.
- Validate schema `0.1` with typed Pydantic models.
- Validate explicit references between sources, tools, memory, outputs, flows, approvals, and exceptions.
- Reject duplicated or ambiguous flow-addressable IDs.
- Reject repeated nodes in a flow.
- Enforce top-level `approvals` as the only approval declaration surface.
- Reject flow declarations that understate source or memory sensitivity.
- Return normalized validation errors and fail-closed exit codes.
- Run without network access, credentials, telemetry, or an LLM API.

## Not implemented yet

- Security-rule evaluation (`RH-AWE-001` through `RH-AWE-008`).
- Finding severities, blocking decisions, or accepted-exception processing.
- Markdown or JSON security reports.
- Runtime inspection, prompt execution, tool execution, or dynamic red teaming.
- Proof that a workflow is secure.

A successful validation result means only that the declaration is structurally, referentially, and semantically consistent with schema `0.1`.

## Installation

Python 3.12 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Validation-only quick start

```bash
rackhead-eval examples/sample-agent-workflow.yaml
```

Expected output:

```text
valid: demo-support-agent (schema 0.1)
```

Validate an optional policy file as well:

```bash
rackhead-eval examples/sample-agent-workflow.yaml \
  --policy examples/sample-policy.yaml
```

Invalid workflow or policy input returns exit code `2`. Unexpected internal evaluator failure returns exit code `3`. Neither path may be reported as success.

## Local checks

```bash
ruff check .
ruff format --check .
mypy
pytest
```

The test suite uses synthetic data and reserved invalid domains. It requires no secrets or network access.

## Repository status

This repository is defensive, early-stage, and not a production security guarantee. Contributions must preserve deterministic behavior, fail-closed validation, safe examples, and the approved trust boundaries in `docs/v0.1-spec.md`.

## Responsible security note

Do not use this repository to publish exploit code against real systems, credential theft, malware, stealth tooling, or instructions for unauthorized access.

## License

MIT unless otherwise noted.
