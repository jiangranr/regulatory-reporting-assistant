# Document Extraction Evaluation

Use for prospectus, announcement, PDF, OCR, table extraction, and fixed-element field extraction projects.

## Extraction Pipeline

1. Ingest document and record source metadata.
2. Classify document type and applicable extraction template.
3. Segment pages, paragraphs, tables, and attachments.
4. Extract candidate fields with source evidence.
5. Normalize values using dictionaries, date rules, amount units, and product rules.
6. Validate fields against business constraints.
7. Generate review view with source location and confidence.
8. Write approved values into enterprise systems through controlled integration.

## Field Definition Template

| Item | Required Content |
|---|---|
| Field name | Business name and system field name |
| Meaning | Business definition and usage |
| Source pattern | Where it appears in documents |
| Format | Data type, unit, date format, enum |
| Normalization | Unit conversion, dictionary mapping, canonical value |
| Validation | Required/optional, range, cross-field checks |
| Evidence | Page, paragraph, table cell, bounding box if available |
| Review rule | Auto-pass, sampled review, mandatory human review |

## Evaluation Metrics

| Metric | Meaning |
|---|---|
| Field precision | Extracted values that are correct |
| Field recall | Required values successfully extracted |
| Exact match | Value matches expected output exactly |
| Normalized match | Value differs in format but normalizes correctly |
| Evidence accuracy | Source position supports the extracted value |
| Review workload | Fields requiring manual correction or confirmation |
| Writeback success | Approved fields written successfully and idempotently |

## Error Taxonomy

- Missing field.
- Wrong source paragraph or table.
- Wrong unit or date normalization.
- Wrong business synonym mapping.
- Conflicting values not detected.
- Low-confidence value auto-accepted.
- Human review UI lacks evidence.
- Writeback fails or duplicates data.

## Governance Rules

- Keep original document, extracted value, normalized value, source evidence, model/tool version, reviewer, and final writeback result.
- Do not overwrite enterprise-system values without before/after comparison.
- For low-confidence or conflicting fields, route to human review.
- Treat OCR and LLM extraction as untrusted until validated by rules or review.

