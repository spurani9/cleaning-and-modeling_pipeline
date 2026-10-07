# Evaluation Specification

## Deterministic stakeholder evals
The offline harness in `evals/run_evals.py` covers all six stakeholder questions from `BUSINESS_CONTEXT.md` and compares query results to golden values, not merely whether a query returned rows.

### Account-level definitions
- **Account snapshot:** one row per `account_id`, selected from the latest observed `invoice_date`, then `invoice_id` as a stable tie-breaker.
- **Active account:** `churned = false` on that snapshot.
- **Average MRR per region:** average `accounts.mrr_usd` across active accounts in each region; choose the highest region.
- **Churn rate:** `churned accounts / all accounts` within the requested plan, using the account snapshot.
- **Top-account revenue:** sum `recognized_revenue_usd` by `account_id`; join the one-row account snapshot for the latest account name and latest CSAT. This prevents inconsistent historical account names from splitting one customer into multiple leaderboard rows.
- **Paid revenue:** when the stakeholder explicitly says “paid invoices”, use only `status='paid'`; refunded rows are handled separately by the refunds question.
- **Refunds:** positive absolute value of the negative `amount_usd` for `status='refunded'`.
- **Pending/failed exposure:** count and USD sum of normalized `pending` + `failed` invoice rows.

## Golden results for the supplied dataset
- Paid 2024 revenue: **$32,686,371.05**
- Highest active-account average MRR region: **APAC ($6,154.42/account)**
- Refunds: **$8,893,303.77**
- Enterprise churn: **21.92%**; Starter churn: **18.83%**
- Top five accounts: Stark Inc ($1,210,592.75), Tyrell Industries ($1,208,092.75), Initech LLC ($1,205,642.75), Pied Piper Partners ($1,107,352.84), Oscorp Industries ($1,085,078.48). None has CSAT <= 2; Tyrell Industries has no CSAT value.
- Pending/failed exposure: **894 invoices / $28,983,255.81**

## Live-model eval
`evals/run_live_evals.py` sends the six natural-language stakeholder questions through the configured LLM planner, validates the generated SQL, executes it, and compares the normalized result rows to the same golden answers.

The live eval is deliberately separate from CI/offline tests because it requires an external model/API and can fail for model/provider reasons even when the deterministic system is correct.

## Expected failure / limitation
The system should not pretend it can answer historical subscription-state questions such as:
> “What was each account's MRR immediately before it churned?”

The supplied ledger has invoice rows plus a current `churned` attribute, but no subscription-state event history. A correct system should surface this as unsupported rather than inventing a historical state.
