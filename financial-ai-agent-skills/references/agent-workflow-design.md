# Agent Workflow Design

Use for single-agent, multi-agent, tool-calling, context engineering, and AI application workflow design.

## Agent Design Template

| Item | Definition |
|---|---|
| Agent role | Specific job responsibility, not a broad persona |
| Input | User request, document, metadata, database schema, workflow state |
| Context | Business rules, field dictionary, examples, policy constraints, previous decisions |
| Tools | MCP tools, internal APIs, database readers, parsers, validators, workflow actions |
| Output | Structured JSON, draft answer, recommended action, API call plan, review report |
| Stop condition | Clear completion criteria and when to ask for human confirmation |
| Risk control | Permission check, validation, confidence threshold, audit, fallback |

## Workflow Rules

- Prefer deterministic tools for parsing, validation, calculation, and database lookup.
- Use the model for language understanding, mapping, reasoning, and exception explanation.
- Do not let the model invent system state. Retrieve state from authoritative systems.
- Separate "plan generation" from "action execution" for write operations.
- Require human confirmation before external writeback unless the process has explicit automation approval.
- Store enough context to reproduce the decision, but avoid storing sensitive raw prompts unnecessarily.

## Multi-Agent Use

Use multiple agents only when responsibilities differ clearly:

| Agent | Good Responsibility |
|---|---|
| Extractor | Convert document or request into structured candidate facts |
| Validator | Check candidates against rules, dictionaries, schemas, and source evidence |
| Planner | Decide next tool call or workflow step |
| Executor | Invoke approved APIs and return execution status |
| Reviewer | Explain risks, uncertainty, and human review items |

Avoid multi-agent designs when a single structured pipeline with validation is simpler and more auditable.

## Context Checklist

- Business dictionary and synonyms.
- Table/API/field schema.
- Positive and negative examples.
- Permission and action boundary.
- Required output format.
- Known failure cases.
- Evaluation cases and expected answers.

## Output Contract

For production-oriented workflows, require structured output with:

- `result`: machine-readable result.
- `confidence`: bounded confidence or rule-based status.
- `evidence`: source paragraph, table row, API response id, or rule id.
- `warnings`: uncertainty, missing data, conflicting data, unsupported request.
- `next_action`: ask user, call tool, require review, stop, or fallback.

