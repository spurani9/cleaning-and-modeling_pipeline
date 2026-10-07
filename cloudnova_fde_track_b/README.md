# CloudNova Forward Deployed Engineer — Track B

## What this is
A small production-shaped analytics system for CloudNova's dirty invoice ledger. It turns customer business rules into a governed data contract, cleans and models the ledger deterministically, then uses an LLM only to translate natural-language questions into safe read-only SQL.

This is intentionally scoped to the assessment's ~60-minute build: no frontend, no cloud deployment, and no distributed cluster. The design leaves clear seams for those additions later.

## Architecture
See [`docs/architecture.mmd`](docs/architecture.mmd).

Raw CSV + customer business rules → spec-driven cleaning/modeling → governed invoice dataset → DuckDB analytical view → constrained NL-to-SQL planner → SQL validation → deterministic answer.

## Why Track B
The customer wants to trust financial answers. RAG is not the right primitive for exact aggregation. The LLM therefore performs language interpretation only; SQL/DuckDB performs financial calculations over the governed dataset.

## Key business rules
- List price: Starter $49, Pro $99, Enterprise $299 per seat/month.
- Annual billing maps to the same MRR and is not double-counted.
- EUR→USD 1.08 and GBP→USD 1.27.
- Recognized revenue uses normalized paid/refunded records; pending/failed/void are excluded.
- MRR = list price × seats × (1 - discount_pct/100).

Source: `data/BUSINESS_CONTEXT.md`.

## Deduplication decision
The raw file contains 5,125 rows and 5,000 invoice IDs. Exact duplicate rows are removed first. For remaining conflicting invoice IDs, the exercise needs a deterministic rule because the supplied context does not provide source-system provenance or a source-priority field. This implementation uses the explicit exercise policy `paid > refunded > pending > failed > void` and records the winner in `dedup_reason`.

This is deliberately surfaced as an assumption rather than presented as truth. In a real customer deployment I would request source provenance/timestamps and establish finance-approved survivorship rules before using conflicting records for financial reporting.

## Reproducible setup
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python evals/run_evals.py
```

Live NL query:
```bash
copy .env.example .env  # Windows
# set OPENAI_API_KEY in .env
python -m app "What was our total recognized revenue in USD for paid invoices in 2024?"
```

## Spec-driven workflow
The intended AI workflow is captured in `CLAUDE.md`. The source-of-truth order is:
1. customer briefing;
2. data contract;
3. query contract;
4. evaluation spec.

The important engineering choice is to keep business logic deterministic and testable rather than asking an LLM to invent or calculate it.

## Evaluation
`evals/run_evals.py` covers the six stakeholder question categories. The pipeline tests verify the governed schema. SQL guardrail tests verify that mutation/multi-statement SQL is rejected.

A future improvement is a live planner eval that runs the six natural-language prompts through the configured model and compares the resulting normalized result to canonical answers. That is intentionally separate from the offline eval so CI does not depend on an external model/API.

## Known limitations / expected failure modes
- Ambiguous numeric dates are parsed using the documented exercise convention and flagged. A production system should preserve raw values and obtain source-system semantics where possible.
- Conflicting duplicate invoice IDs require an exercise-level survivorship rule because the customer briefing does not specify source authority.
- The current query planner requires an OpenAI-compatible API key for live NL-to-SQL.
- LLM-generated SQL can still be semantically wrong while syntactically safe; the evaluation suite is the control, not SQL validation alone.
- Churn rate is defined here at the invoice-row/account representation available in the supplied dataset. A production customer would need an explicit subscription/account snapshot definition if multiple rows per account can represent materially different states.

## What I would do with another day
- Add source provenance and finance-approved survivorship rules.
- Persist the governed model in a warehouse/lakehouse and use dbt tests.
- Add a semantic metric layer for recognized revenue, MRR and churn definitions.
- Add model-based NL query evaluation with golden SQL and result equivalence checks.
- Add OpenTelemetry metrics, structured logs and CI/CD.
- Add authentication and tenant isolation for a deployed API.

## Production-hardening touch
The repository includes SQL guardrails, typed query contracts, deterministic transformations, automated tests, an offline eval harness, `.env` configuration, and a Dockerfile-ready dependency set rather than hard-coded secrets.
