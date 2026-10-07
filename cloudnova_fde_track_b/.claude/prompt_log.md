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

## Prompt 5 — Stakeholder correctness review
Re-run all six stakeholder questions as deterministic golden-result evals. Do not treat “query returned rows” as success. Explicitly define account-level metrics and distinguish “paid invoices” from net recognized revenue including refunds.

## Prompt 6 — Query safety hardening
Strengthen the NL-to-SQL boundary with schema-aware structured output, governed table declarations, static SQL safety checks, filesystem/network escape-hatch blocking, and DuckDB EXPLAIN validation before execution. Keep the LLM responsible for query structure, not financial arithmetic.

## Review findings corrected
- Q1 now filters `status='paid'` because the stakeholder wording explicitly says “paid invoices”; refunds are evaluated separately.
- Q5 aggregates revenue by `account_id`, then joins the latest account snapshot for account name and latest CSAT. Grouping by historical `account_name` could split one customer because the dirty export contains inconsistent names.
- Offline evals now compare actual result values against golden answers.
- A separate live-model eval runs the six natural-language prompts through the configured model and compares normalized results to the deterministic goldens.
- An unsupported historical-MRR question is documented as an expected limitation rather than allowing the agent to fabricate subscription history.
