# Java Backend Rules

Use for Spring Cloud, Spring Boot, MySQL, workflow, and enterprise integration work.

## Design Rules

- Define the API contract before implementation: request schema, response schema, error code, idempotency key, permission model.
- Keep controller logic thin. Put orchestration in application services and business rules in domain/service classes.
- Keep persistence models separate from external DTOs when data is sensitive or contracts are stable.
- Use transactions only around the smallest required consistency boundary.
- Treat external API calls, model calls, and file parsing as unreliable dependencies with timeout, retry, fallback, and audit logging.
- For financial write operations, design idempotency, duplicate prevention, and reconciliation before writing code.

## API Checklist

| Area | Requirement |
|---|---|
| Validation | Validate required fields, formats, ranges, enum values, and cross-field consistency |
| Errors | Return stable business error codes and avoid leaking stack traces |
| Permissions | Check user, role, data scope, operation scope, and tenant/institution scope |
| Idempotency | Required for writeback, workflow transition, file import, and external invocation |
| Audit | Log operator, source system, request id, business key, before/after state, result |
| Observability | Correlation id, latency, dependency status, model/tool version where relevant |
| Compatibility | Avoid breaking existing consumers; version public contracts when needed |

## MySQL/Data Rules

- Never let AI-generated SQL execute directly against write-capable connections.
- Use parameterized queries and typed repositories/mappers.
- For reference/static data, preserve effective date, status, source, version, and audit fields.
- For batch imports, record batch id, row-level errors, success/failure counts, and replay strategy.
- For regulatory or clearing-related data, retain original source values when normalization is applied.

## Testing Baseline

- Unit test domain rules and mapping logic.
- Integration test database transactions, MyBatis/JPA queries, and external API adapters.
- Contract test APIs that will be called by Agent tools or workflow engines.
- Regression test known bug cases, boundary data, duplicate requests, permission denial, and timeout behavior.

## Review Questions

- Can this operation be safely retried?
- What happens if the external system succeeds but our system times out?
- Is the audit record enough to reconstruct who did what and why?
- Can a user access data outside their institution, product, or role?
- Is the model/Agent output treated as untrusted input?

