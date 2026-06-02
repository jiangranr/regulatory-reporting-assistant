# Production Readiness

Use before pilot, release, production use, demo-to-product transition, or project packaging.

## Readiness Checklist

| Area | Required Evidence |
|---|---|
| Business owner | Owner, target users, process location, review responsibility |
| Scope | Supported scenarios, unsupported scenarios, non-goals |
| Data security | Data classification, permission check, masking, retention policy |
| Model risk | Hallucination controls, validation, confidence, human review |
| Integration | API contract, idempotency, timeout, retry, reconciliation |
| Evaluation | Test set, metrics, regression process, known limitations |
| Observability | Logs, metrics, alerts, tracing, cost and latency monitoring |
| Fallback | Manual process, degraded mode, rollback plan |
| Audit | Input, output, action, reviewer, system state, version records |
| Operations | Support owner, runbook, incident response, change process |

## Launch Modes

| Mode | Use When | Controls |
|---|---|---|
| Demo | Proving concept | Synthetic/sample data, no production claim |
| Pilot | Real users in controlled scope | Human review, limited data/action scope |
| Assisted production | Real process with human confirmation | Audit, monitoring, fallback, maker-checker |
| Automated production | Low-risk repeated action with approval | Strong validation, rollback, alerting, governance signoff |

## Monitoring Signals

- Request volume and active users.
- Success, failure, timeout, and fallback rates.
- Manual correction rate.
- High-risk block rate.
- Average and P95 latency.
- Cost per request or per document.
- External API error rate.
- Regression case pass rate after changes.

## Incident Questions

- Can we identify affected users, documents, records, and downstream systems?
- Can we reconstruct the input, output, tool call, model version, and reviewer?
- Can we stop the automation without stopping the whole business process?
- Can we roll back or compensate incorrect writeback?
- Which evaluation case should be added to prevent recurrence?

## Packaging for Reviews

When packaging a project for interview, award, or leadership review, include:

1. Business pain point.
2. Architecture and integration diagram.
3. AI capability boundary.
4. Evaluation and governance mechanism.
5. Pilot or production evidence.
6. Quantified or bounded value.
7. Risks, limitations, and next step.

