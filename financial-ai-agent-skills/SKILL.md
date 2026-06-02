---
name: financial-ai-application-delivery
description: Use when designing, building, reviewing, testing, or packaging financial AI applications, especially Java backend systems, NL-to-SQL agents, document extraction agents, MCP/API integrations, governance evidence, regression evaluation, and production readiness.
---

# Financial AI Application Delivery

## Core Principle

Treat financial AI work as enterprise application delivery, not a model demo. Every output must make boundaries, evidence, risk controls, integration points, and human review responsibilities explicit.

## Default Workflow

Use this workflow for AI application features, project packaging, architecture reviews, and delivery planning:

1. Define the business scenario, target user, input, output, system boundary, and non-goals.
2. Identify financial data sensitivity, permissions, audit needs, and human review points.
3. Design the backend/API/Agent contract before implementation.
4. Create evaluation and regression cases before expanding features.
5. Implement in small slices with observable logs and failure handling.
6. Review for security, consistency, idempotency, rollback, and operational evidence.
7. Package the outcome as reusable project evidence: architecture, metrics, governance, and limitations.

## Reference Selection

Load only the reference files needed for the task:

| Task | Read |
|---|---|
| Requirements, project scope, award/resume packaging | `references/financial-ai-spec.md` |
| Java backend design or implementation | `references/java-backend-rules.md` |
| Agent workflow, tools, context, multi-agent design | `references/agent-workflow-design.md` |
| NL-to-SQL capability, SQL generation, query safety | `references/nl2sql-safety.md` |
| Prospectus, announcement, PDF, OCR, field extraction | `references/document-extraction-eval.md` |
| MCP tools, enterprise API invocation, writeback | `references/mcp-integration-rules.md` |
| Evaluation sets, regression tests, model changes | `references/ai-regression-testing.md` |
| Trial launch, production readiness, monitoring, fallback | `references/production-readiness.md` |

## Output Rules

- Lead with conclusion, then evidence, then next action.
- Separate facts from assumptions and proposals.
- Do not claim production use, measurable value, compliance approval, or model accuracy unless evidence is available.
- Prefer tables and checklists for reusable work products.
- For financial scenarios, always include data security, permissions, auditability, human review, fallback, and cost/latency considerations.

