# Natural-Language Query Contract

## Goal
Translate stakeholder questions into safe, auditable SQL over the governed `invoices` view.

## LLM output contract
The planner must return JSON:
```json
{"sql":"SELECT ...","explanation":"..."}
```

## Safety
- SELECT statements only.
- Only the governed `invoices` and `accounts` views may be referenced.
- No PRAGMA, ATTACH, COPY, INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, EXPORT or filesystem functions.
- No multiple statements.
- SQL is validated before execution.
- User text is never interpolated into SQL parameters.

## Design principle
The LLM chooses query structure; SQL/DuckDB performs all arithmetic, filtering, grouping and aggregation. The LLM is not trusted to calculate financial answers itself.

## Answer contract
Return: natural-language answer, generated SQL, row count, and execution metadata. For stakeholder-facing output, state important assumptions such as the deduplication policy and fixed FX rates when relevant.
