# Markdown Report Format Draft

Status: early MVP design. Reports should be easy to read in GitHub issues and pull requests.

## Report structure

```markdown
# Agent Workflow Security Review

## Summary

- Workflow: <name>
- Deployment stage: <stage>
- Max autonomy: <level>
- Overall risk: low | medium | high | review_required

## Findings

### RH-AWE-001: External write without approval

- Severity: high
- Evidence: tool `send_email` has mode `external_write` and `requires_approval: false`
- Why it matters: external writes can publish private or manipulated content
- Suggested fix: require approval, restrict recipients/domains, and log tool arguments

## Data-boundary notes

## Tool permission notes

## Memory notes

## Monitoring notes

## Limitations

This report is a static design review. It does not prove runtime security.
```

## Output principles

- Prefer clear evidence over vague warnings.
- Include exact YAML paths when possible.
- Avoid panic language.
- Always state limitations.
- Keep recommendations defensive and practical.
