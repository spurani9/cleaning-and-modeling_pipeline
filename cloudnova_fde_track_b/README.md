# CloudNova Forward Deployed Engineer — Track B

## 1. What I built

CloudNova's finance lead has a dirty invoice ledger and wants trusted answers to revenue/customer questions in plain English.

This Track B solution uses a **spec-driven cleaning/modeling pipeline + constrained NL→SQL query agent**:

```text
raw CSV
  ↓
spec-driven normalization + deterministic business rules
  ↓
governed invoice table + one-row-per-account snapshot
  ↓
DuckDB
  ↓
natural language → typed query plan → SQL guardrails → schema validation
  ↓
deterministic result + generated SQL + assumptions
```

The LLM interprets language. **It does not calculate revenue, MRR, refunds or churn.** Those calculations happen in the governed data model / SQL layer.

## 2. Why this design

Track B fits the customer's requirement for trustworthy aggregation better than pure RAG. The supplied business context defines exact financial rules, so the safest architecture is:

- make the business rules executable and testable;
- make the cleaned schema the LLM's only semantic surface;
- constrain generated SQL to read-only governed views;
- validate the SQL before execution;
- compare the system against stakeholder-level golden answers.

The assessment explicitly prioritizes Spec-Driven Development, AI steering, evaluation/honesty, production instincts and communication. It does **not** score cloud deployment or UI polish, so the implementation stays deliberately small.

## 3. Run it

### Setup

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Deterministic tests + stakeholder evals

These do not require an API key:

```bash
pytest -q
python evals/run_evals.py
```

The six offline evals compare the actual SQL result to golden answers. A test that merely returns rows is not considered a pass.

### Live natural-language demo

Copy `.env.example` to `.env` and provide an OpenAI-compatible API key:

```bash
# Windows
copy .env.example .env
# macOS/Linux
cp .env.example .env

python -m app "What was our total recognized revenue in USD for paid invoices in 2024?"
```

The output contains the question, result rows, generated SQL, planner explanation, assumptions and row count.

For the assessment walkthrough, run all six stakeholder questions:

```bash
python -m app --demo
```

### Live-model evaluation

```bash
python evals/run_live_evals.py
```

This sends the six natural-language questions through the configured model, validates the generated SQL, executes it, and compares normalized results to the same golden answers used by the deterministic eval.

## 4. The six stakeholder questions

The supplied `BUSINESS_CONTEXT.md` seeds these six cases:

1. Total recognized revenue in USD for paid invoices in 2024.
2. Region with the highest average MRR per account.
3. Total refunds.
4. Enterprise vs Starter churn rate.
5. Top 5 accounts by revenue with a CSAT ≤ 2 flag.
6. Pending/failed invoice count and exposed USD.

### Golden results for this supplied dataset

| Question | Deterministic result |
|---|---:|
| Paid 2024 revenue | **$32,686,371.05** |
| Highest active-account avg MRR | **APAC — $6,154.42/account** |
| Refunds | **$8,893,303.77** |
| Enterprise churn | **21.92%** |
| Starter churn | **18.83%** |
| Pending/failed exposure | **894 invoices — $28,983,255.81** |

Top 5 by recognized revenue:

| Account | Revenue | CSAT ≤ 2? |
|---|---:|:---:|
| Stark Inc | $1,210,592.75 | No |
| Tyrell Industries | $1,208,092.75 | No — CSAT unavailable |
| Initech LLC | $1,205,642.75 | No |
| Pied Piper Partners | $1,107,352.84 | No |
| Oscorp Industries | $1,085,078.48 | No |

The leaderboard groups revenue by **account_id**, then joins the latest account snapshot. This matters because the dirty export can contain inconsistent historical account names for one account.

## 5. Business rules encoded in the spec

Source of truth: [`data/BUSINESS_CONTEXT.md`](data/BUSINESS_CONTEXT.md).

- Starter = $49, Pro = $99, Enterprise = $299 per seat/month.
- Annual invoices represent 10 billed months and map to the same underlying MRR; annual lump sums are not divided into recognized revenue or double-counted as MRR.
- Fixed exercise FX: EUR→USD 1.08, GBP→USD 1.27, USD→USD 1.00.
- Recognized revenue is `amount_usd` for normalized `paid` and `refunded` records; pending/failed/void contribute zero. When the stakeholder explicitly asks for **paid invoices**, the query uses only `status='paid'`.
- MRR is `list_price × seats × (1 - discount_pct/100)`.
- Status, plan, billing-cycle and boolean variants are normalized deterministically.
- Amount strings, malformed emails, nulls and mixed dates are handled by the data contract.

## 6. Account-level definitions

The source is an invoice ledger, not a subscription-event system. Therefore the implementation creates an **account snapshot**:

- one row per `account_id`;
- latest observed `invoice_date`, then `invoice_id` as a stable tie-breaker;
- `active = not churned`;
- MRR/churn/latest CSAT questions use this snapshot;
- region MRR averages only active accounts;
- churn rate = churned accounts / all accounts within the plan;
- top-account revenue aggregates invoices by `account_id` and then joins the latest snapshot.

This is an explicit exercise-level modeling choice. A production implementation should replace it with true subscription-state/event history if available.

## 7. Duplicate and date decisions

The raw export contains **5,125 physical rows and 5,000 invoice IDs**. Exact duplicates are removed first. Remaining duplicate invoice IDs are resolved deterministically using the exercise policy:

`paid > refunded > pending > failed > void`

The winning record is retained with an audit `dedup_reason`. This is **not** claimed to be real finance-system source authority; the customer briefing does not provide provenance or source priority. In a real engagement, I would request source timestamps/provenance and obtain a finance-approved survivorship rule.

Numeric dates are parsed using the documented MM/DD convention when necessary and flagged with `date_parse_warning`. The supplied dataset contains **612 potentially ambiguous numeric dates** under that rule.

## 8. NL→SQL guardrails

The planner returns typed structured output:

- intent;
- generated SQL;
- declared governed tables;
- explanation;
- material assumptions.

Before execution:

1. Pydantic validates the response shape.
2. SQL must be exactly one `SELECT` statement.
3. Only `invoices` and `accounts` are allowed.
4. Mutation/admin statements are rejected.
5. Filesystem/network/extension escape-hatch functions are rejected.
6. Planner-declared tables must match the relations actually used by the SQL.
7. DuckDB `EXPLAIN` validates the query against the live governed schema.
8. Only then is the query executed.

These controls address **syntactic safety**. They do not guarantee semantic correctness; that is why the stakeholder evals are a first-class artifact.

## 9. Spec-driven AI workflow

The repository keeps the AI steering artifacts visible because the assessment explicitly asks to see how AI was directed.

- [`CLAUDE.md`](CLAUDE.md) — engineering instructions and source-of-truth order.
- [`.claude/prompt_log.md`](.claude/prompt_log.md) — trimmed prompt/decision history.
- [`specs/data_contract.md`](specs/data_contract.md) — schema, normalization, deduplication and metric rules.
- [`specs/query_contract.md`](specs/query_contract.md) — structured planner and SQL safety contract.
- [`specs/eval_spec.md`](specs/eval_spec.md) — stakeholder definitions, golden results and expected limitation.

The important direction to the coding agent was: **read the customer briefing first, write the spec before implementation, keep financial logic deterministic, and review generated code for double-counting, ambiguity and unsafe SQL.**

## 10. Known limitations / honest failure modes

- **Conflicting invoice duplicates:** survivorship is an exercise assumption because the source lacks provenance.
- **Ambiguous dates:** a documented convention is used and flagged; production reporting should preserve the raw value and obtain source semantics.
- **Account history:** current churn/plan/CSAT are represented by the latest invoice snapshot; historical subscription state is not available.
- **LLM semantic errors:** safe SQL can still be the wrong SQL. The live eval exposes this rather than hiding it.
- **Expected unsupported question:** “What was each account's MRR immediately before it churned?” should not be fabricated because the dataset has no subscription-state event history.
- **Live model dependency:** `evals/run_live_evals.py` requires an external model/API and is intentionally separate from offline CI tests.

## 11. What I would do with another day

1. Add source provenance and finance-approved duplicate survivorship rules.
2. Replace the account snapshot with a true subscription/event model.
3. Add a semantic metric layer for revenue, MRR and churn definitions.
4. Add richer query-result citations back to invoice IDs for audit workflows.
5. Add CI to run deterministic tests/evals and optionally a scheduled live-model regression suite.
6. Add structured logs, latency/cost metrics and OpenTelemetry around the planner.
7. Package the service behind an authenticated API with tenant isolation.

## 12. Repository map

```text
app/
  pipeline.py        deterministic cleaning + modeling
  query_agent.py     typed NL→SQL planner + guardrails
  main.py            CLI/demo
  config.py          environment-driven runtime config
specs/
  data_contract.md   source-derived data/metric contract
  query_contract.md  planner/safety contract
  eval_spec.md       stakeholder definitions + golden answers
evals/
  run_evals.py       offline deterministic stakeholder eval
  run_live_evals.py  live model regression eval
tests/
  test_pipeline.py
  test_sql_guardrail.py
docs/
  architecture.mmd
.claude/
  prompt_log.md
CLAUDE.md
Dockerfile
```

## 13. 3–5 minute walkthrough

**0:00–0:45 — Problem/spec.** Show `BUSINESS_CONTEXT.md` → `specs/data_contract.md`. Explain that the business rules are encoded before asking AI to write transformation code.

**0:45–1:30 — Architecture.** Open `docs/architecture.mmd`. Point out raw CSV → deterministic pipeline → governed views → LLM planner → SQL guardrails → DuckDB.

**1:30–2:30 — Correctness.** Run `python evals/run_evals.py`. Show all six stakeholder cases passing against golden answers. Mention the explicit account-snapshot definitions.

**2:30–3:30 — AI use + safety.** Open `.claude/prompt_log.md` and `app/query_agent.py`. Run one natural-language question and show the generated SQL alongside the result.

**3:30–4:15 — Honesty/trade-offs.** Show duplicate/date assumptions and the expected unsupported historical-MRR question. Explain what you would do with source provenance and subscription events.

**4:15–5:00 — Live eval (optional).** Run `python evals/run_live_evals.py` if an API key is configured and show model-generated SQL being compared with deterministic golden results.
