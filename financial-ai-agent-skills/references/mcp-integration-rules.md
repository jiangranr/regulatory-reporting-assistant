# MCP Integration Rules

Use for MCP-style tools, enterprise API invocation, workflow actions, and system writeback.

## Tool Contract

Every tool/API exposed to an Agent must define:

- Purpose and business owner.
- Input schema and validation.
- Output schema and stable error codes.
- Permission model and data scope.
- Idempotency behavior.
- Timeout and retry policy.
- Audit fields.
- Whether it is read-only, write-with-confirmation, or write-automatic.

## Tool Risk Levels

| Level | Examples | Required Control |
|---|---|---|
| Read-only | Query reference data, fetch workflow status | Permission check, query limit, audit |
| Draft action | Generate payload, prepare workflow comment | Human confirmation before submit |
| Controlled write | Update extracted fields, submit review result | Idempotency key, approval state, before/after audit |
| High-risk write | Payment, clearing instruction, regulatory submission | Usually not suitable for autonomous Agent execution |

## Execution Pattern

1. Agent proposes action and parameters.
2. Backend validates user permission and schema.
3. Backend rechecks authoritative business state.
4. Backend executes with idempotency and correlation id.
5. Backend writes audit record.
6. Agent summarizes result and residual risk.

## Anti-Patterns

- Letting the model call arbitrary URLs or SQL.
- Hiding permission checks inside prompt instructions.
- Using natural language as the only API parameter validation.
- Exposing high-risk write APIs without confirmation.
- Returning unstructured error text that the Agent cannot recover from.
- Missing correlation id across Agent, backend, and external system.

## Audit Record Minimum

- Operator/user id.
- Business object id.
- Tool name and version.
- Request id/correlation id.
- Input parameters after validation.
- External system response summary.
- Before/after state for writes.
- Model or workflow version where relevant.
- Timestamp and final status.

