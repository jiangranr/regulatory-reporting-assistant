# NL-to-SQL Safety

Use for natural-language query, SQL generation, report query, and database question-answering systems.

## Non-Negotiable Safety Rules

- Default to read-only database credentials.
- Block DDL, DML, stored procedure execution, file operations, and administrative statements.
- Use table and column allowlists by scenario, role, and data scope.
- Require SQL AST parsing or structured query generation before execution.
- Apply row-level permission filters outside the model output.
- Limit result size, timeout, and query complexity.
- Log natural language, selected schema, generated SQL, validator result, execution metadata, and returned row count.

## Allowed Flow

1. Classify user intent and business domain.
2. Select allowed tables/columns from metadata.
3. Generate SQL under constraints.
4. Parse and validate SQL.
5. Inject mandatory permission and data-scope filters.
6. Explain the query plan in business terms.
7. Execute with read-only, timeout-limited connection.
8. Return results with caveats and no hidden assumptions.

## Validation Checklist

| Check | Requirement |
|---|---|
| Statement type | Only `SELECT` or approved read-only equivalent |
| Tables | All tables appear in allowlist |
| Columns | Sensitive columns require explicit authorization |
| Joins | Join keys must match metadata-defined relationships |
| Filters | Business date, institution, user data scope, product scope applied |
| Aggregation | Grouping and metrics align with business definitions |
| Limits | Default and maximum row limits enforced |
| Complexity | Block Cartesian joins, unbounded scans, and risky functions |

## Evaluation Set

Maintain cases in these categories:

- Simple lookup.
- Multi-table join.
- Aggregation and ranking.
- Date/effective-date logic.
- Synonyms and business aliases.
- Ambiguous questions requiring clarification.
- Permission-denied questions.
- Unsupported or unsafe requests.
- Known historical failure cases.

## Response Rules

- If the question is ambiguous, ask a clarification instead of guessing.
- If a metric has multiple definitions, list the candidate definitions.
- If data is unavailable or permission-denied, say so plainly.
- Do not expose raw SQL to end users unless they are technical users and the product allows it.

