# Trimmed AI Steering Log

## Prompt 1 — Specification
Read `data/BUSINESS_CONTEXT.md` and the assessment instructions first. Do not write implementation code yet. Produce a minimal deterministic data contract covering schema, normalization, dates, amounts/FX, MRR, revenue, and duplicate handling. Explicitly mark any rule that is an exercise assumption rather than customer-provided truth.

## Prompt 2 — Pipeline
Implement the pipeline from `specs/data_contract.md`. Keep raw data immutable. Add validation and tests. Do not let an LLM calculate financial metrics.

## Prompt 3 — Query agent
Implement NL-to-SQL using `specs/query_contract.md`. Return structured JSON, validate SQL, allow only SELECT against the governed invoices view, and execute calculations in DuckDB.

## Prompt 4 — Evaluation
Create offline deterministic tests for the stakeholder questions and SQL safety. Keep live model evaluation separate so the base test suite remains reproducible without an API key.

## Review instruction
Challenge generated code for double-counting, ambiguous dates, duplicate survivorship, arbitrary SQL execution, silent data loss, secrets, and non-reproducible behavior. Fix issues before adding features.
