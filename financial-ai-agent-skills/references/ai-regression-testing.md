# AI Regression Testing

Use when model behavior, prompts, tools, schemas, parsing rules, or business logic may change AI application output.

## Evaluation Set Structure

| Field | Meaning |
|---|---|
| case_id | Stable identifier |
| scenario | Business scenario or document type |
| input | User question, document snippet, API context, or file reference |
| expected_output | SQL, fields, action plan, answer, or validation status |
| expected_evidence | Source paragraph, table, schema field, or rule id |
| risk_level | Low, medium, high |
| acceptance_rule | Exact match, normalized match, semantic match, manual review |
| tags | Permission, ambiguity, edge case, known bug, regression |

## Test Categories

- Golden path cases.
- Boundary and edge cases.
- Ambiguous inputs requiring clarification.
- Permission-denied or unsupported cases.
- Adversarial prompt injection or unsafe requests.
- Historical production defects.
- High-value business scenarios.
- Low-confidence cases routed to review.

## Change Gate

Before changing model, prompt, parser, tool schema, or business dictionary:

1. Run baseline cases.
2. Compare new outputs with previous accepted outputs.
3. Classify differences as improvement, neutral, regression, or expected business change.
4. Review high-risk differences manually.
5. Record model/prompt/tool version and evaluation summary.

## Metrics

Use metrics that match the task:

- Classification: accuracy, precision, recall, confusion matrix.
- Extraction: field precision/recall, exact match, normalized match, evidence accuracy.
- NL-to-SQL: execution accuracy, result accuracy, safety block accuracy, clarification rate.
- Tool use: parameter accuracy, successful execution rate, unsafe action block rate.
- Operations: latency, timeout rate, cost per request, manual review rate.

## Reporting Template

| Item | Content |
|---|---|
| Change | What changed and why |
| Dataset | Number of cases, scenario coverage, high-risk cases |
| Result | Key metrics and regression count |
| Review | Manual review findings |
| Decision | Release, block, narrow rollout, or rollback |
| Follow-up | New cases added and known limitations |

