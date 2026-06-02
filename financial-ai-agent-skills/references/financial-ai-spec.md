# Financial AI Specification

Use this template before building or packaging a financial AI feature.

## One-Page Spec

| Section | Required Content |
|---|---|
| Project name | Short business-readable name, not only a technical label |
| Business scenario | Where the work appears in the bank, department, product, or operation chain |
| Target users | Business users, operations staff, IT maintainers, reviewers, managers |
| Pain point | Current manual process, repeated judgment, data lookup, document handling, or system switching cost |
| Input | Documents, natural language, database metadata, API payloads, workflow events |
| Output | Structured fields, SQL, answers, task execution, report drafts, audit records |
| System boundary | What the AI can decide, what it can only suggest, what must stay human-reviewed |
| Integration points | Upstream systems, downstream systems, MCP/API tools, databases, workflow engines |
| Non-goals | Explicitly exclude unsupported products, tables, permissions, actions, and decision rights |
| Evaluation | Test set, acceptance threshold, error categories, regression process |
| Governance | Permission, audit, logging, review, fallback, monitoring, cost control |
| Evidence | Pilot status, production status, user feedback, volume, before/after comparison |

## Financial AI Boundary Checklist

- Business semantics: product, institution, counterparty, account, instrument, clearing, report, workflow state.
- Data scope: public data, internal business data, sensitive customer data, regulatory data, confidential documents.
- Authority boundary: read-only query, recommendation, draft generation, API execution, system writeback.
- Human review: which outputs require confirmation, dual control, maker-checker, or sampled review.
- Audit trail: input, prompt/context version, model/tool version, output, reviewer, final action, timestamp.
- Failure mode: hallucination, wrong field mapping, stale metadata, permission leakage, duplicate writeback, timeout.

## Conservative Claiming Rules

- Say "pilot" only when there was real user trial or controlled scenario validation.
- Say "production-used" only when used in a real business process, even if human-reviewed.
- Say "improved efficiency" only with a measured or bounded comparison.
- Say "reduced risk" only when the risk control mechanism is named.
- Say "reusable" only when there is a module, template, workflow, or documented pattern that can be applied again.

## Reusable Output Structure

Use this structure for project reviews, interview answers, or award applications:

1. Business background and pain point.
2. Target users and use cases.
3. End-to-end solution.
4. AI capability and system integration design.
5. Evaluation and governance.
6. Pilot/production evidence and limitations.
7. Reusable assets and next-step expansion.

