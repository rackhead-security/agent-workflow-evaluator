# Agent Workflow Evaluator YAML Schema Draft

Status: early MVP design. This schema is intentionally small and reviewable. It is not a production security guarantee.

## Goals

The evaluator should help a builder describe an agent workflow and receive a defensive review report. It should flag risky patterns such as external writes without approval, private data flowing into public outputs, broad credentials, memory writes without review, and missing logs.

## Top-level fields

```yaml
name: string
version: string
owners:
  - string
risk_profile:
  deployment_stage: toy | internal | production
  max_autonomy: draft_only | read_only | approved_actions | autonomous_actions
data_sources:
  - name: string
    type: document_store | web | email | chat | database | file_system | api | synthetic
    trust: trusted | mixed | untrusted
    contains_sensitive_data: boolean
    access_control: none | user_scoped | service_scoped | repository_scoped
tools:
  - name: string
    mode: read | internal_write | external_write | destructive | code_execution
    identity: user_delegated | service_account | anonymous | unknown
    requires_approval: boolean
    allowed_domains: []
    allowed_paths: []
    logs_arguments: boolean
    logs_results: boolean
memory:
  enabled: boolean
  writes_allowed: boolean
  review_required: boolean
  retention: none | session | fixed_days | indefinite
outputs:
  - name: string
    type: chat | file | email | ticket | api | public_web | code_change
    external: boolean
approvals:
  - action: string
    required_for: []
monitoring:
  log_tool_calls: boolean
  log_retrieved_sources: boolean
  alert_on_external_write: boolean
  alert_on_policy_block: boolean
```

## Initial static checks

| Check ID | Severity | Condition | Defensive reason |
|---|---:|---|---|
| RH-AWE-001 | high | external_write tool without approval | Prevent unintended messages, leaks, or publication |
| RH-AWE-002 | high | destructive tool without approval | Prevent deletion or irreversible actions |
| RH-AWE-003 | high | mixed/untrusted source plus external output | Prompt injection and data-boundary risk |
| RH-AWE-004 | medium | memory writes allowed without review | Memory poisoning risk |
| RH-AWE-005 | medium | missing tool-call logs | Weak incident response and debugging |
| RH-AWE-006 | medium | code_execution tool in non-toy workflow | Sandbox and execution risk |
| RH-AWE-007 | high | sensitive data source with public/external output | Data exfiltration risk |
| RH-AWE-008 | low | unknown identity | Weak auditability |

## Non-goals

- It does not prove a workflow is secure.
- It does not execute prompts or exploit systems.
- It does not scan real credentials.
- It does not replace human review.
