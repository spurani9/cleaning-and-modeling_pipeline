# Natural-Language Query Contract

## Goal
Translate stakeholder questions into safe, auditable SQL over the governed `invoices` and `accounts` views.

## Structured planner output
The planner returns typed JSON:
```json
{
  "intent": "revenue|mrr|churn|refunds|exposure|account_revenue|other",
  "sql": "SELECT ...",
  "tables": ["invoices"],
  "explanation": "short explanation",
  "assumptions": ["material assumptions"]
}
```

The prompt is schema-aware: it supplies the governed columns, types, canonical categories and metric definitions. Pydantic validates the structure before SQL execution.

## Safety guardrails
- Exactly one SELECT statement.
- Only `invoices` and `accounts` may be referenced.
- Mutation/admin statements are rejected.
- Filesystem/network/extension escape-hatch functions are rejected.
- Planner-declared tables must match the tables actually referenced by SQL.
- DuckDB `EXPLAIN` validates the generated query against the live governed schema before execution.
- User text is never interpolated into SQL.

## Semantic guardrails
- The model must use `recognized_revenue_usd` for recognized revenue, not invent an amount calculation.
- Explicit “paid invoices” means `status='paid'`.
- MRR comes from `mrr_usd` and account-level MRR questions use `accounts`.
- Churn is calculated from the account snapshot.
- Refunds are separated from paid revenue and reported as a positive amount returned.
- Annual invoice amounts are never divided by 12.

## Design principle
The LLM chooses query structure; the deterministic pipeline and DuckDB perform filtering, arithmetic, grouping and aggregation. The LLM is not trusted to calculate financial answers itself.

## Answer contract
The runtime returns the natural-language question, generated SQL, result rows, explanation, assumptions and row count. This makes the generated query directly inspectable during a stakeholder demo.
