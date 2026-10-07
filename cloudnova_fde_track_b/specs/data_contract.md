# CloudNova Clean Data Contract

## Objective
Create a governed invoice table from the raw export. Financial metrics must be deterministic and reproducible.

## Canonical columns
- `invoice_id`: string, required, unique after deduplication.
- `account_id`: string, required.
- `account_name`: string, required.
- `contact_email`: nullable string; normalize `_at_` to `@` only when the result has a valid single `@` shape; otherwise null.
- `region`: nullable enum `NA|EMEA|APAC|LATAM`.
- `industry`: nullable string.
- `plan`: enum `starter|pro|enterprise`.
- `billing_cycle`: enum `monthly|annual`.
- `seats`: positive integer.
- `currency`: enum `USD|EUR|GBP`.
- `amount_local`: decimal.
- `amount_usd`: decimal using fixed FX: USD=1.0, EUR=1.08, GBP=1.27.
- `discount_pct`: decimal in [0,100].
- `status`: enum `paid|pending|failed|refunded|void`.
- `payment_method`: nullable enum `credit_card|ach|wire|invoice`.
- `signup_date`: date.
- `invoice_date`: date.
- `churned`: boolean.
- `csat_score`: nullable decimal in [1,5].
- `support_tickets`: non-negative integer.
- `mrr_usd`: decimal calculated from plan price, seats and discount.
- `recognized_revenue_usd`: decimal; amount_usd only when status is paid or refunded, otherwise zero.
- `dedup_reason`: audit string.

## Normalization
Plan: `starter/start/tier 1 -> starter`; `pro/professional/tier 2 -> pro`; `enterprise/ent/tier 3 -> enterprise`.

Billing cycle: `monthly -> monthly`; `annual/annually/yearly -> annual`.

Status: use the exact canonical mappings in `BUSINESS_CONTEXT.md`.

Payment method: `credit card/credit_card -> credit_card`; `ach -> ach`; `wire/wire transfer -> wire`; `invoice -> invoice`.

Boolean: `true/TRUE/Yes/1/Y -> true`; `false/FALSE/No/0/N -> false`.

## Dates
Parse ISO, slash-separated US-style dates, month-name dates, and unambiguous day-first dash dates. For a numeric slash date, interpret as MM/DD/YYYY because the dataset contains values such as 06/23/2023 that cannot be DD/MM/YYYY. For dash dates where both day and month are <=12, use the same MM-DD-YYYY convention; where one component exceeds 12, interpret it as the day component. Ambiguous dates are flagged in `date_parse_warning` rather than silently treated as certain.

## Amounts
Strip currency symbols, commas and whitespace. A trailing currency code is allowed. The authoritative currency is the row's `currency` column. Reject rows where the numeric amount cannot be parsed.

## Deduplication
1. Remove exact duplicate rows.
2. For remaining duplicate `invoice_id`s, collapse to one canonical row using deterministic status precedence: `paid > refunded > pending > failed > void`.
3. If multiple remaining rows tie on status, choose the first occurrence after stable source ordering.
4. Record `dedup_reason` as `normalized_duplicate_resolved` when normalized fields agree, or `conflicting_invoice_id_resolved:<winner_status>` when normalized status conflicts.
5. This is an exercise-level policy, not a claim about CloudNova's real source-system authority. In a production engagement, source provenance/timestamps should be added before choosing financial precedence.

## Revenue and MRR
List prices: starter=49, pro=99, enterprise=299 USD/seat/month.

`mrr_usd = list_price * seats * (1 - discount_pct / 100)`.

`recognized_revenue_usd = amount_usd` for `paid` and `refunded`; otherwise `0`. Annual invoices do not alter MRR and are not divided by 12 for recognized revenue.


## Account snapshot
Because the source is an invoice ledger, repeated invoices must not be treated as repeated active subscriptions. Build one `accounts` governed view using the latest observed invoice per `account_id` (invoice_date, then invoice_id as stable tie-breaker). The latest account name, plan, region, churn flag and CSAT come from this snapshot.

Account-level definitions:
- active account = `churned = false` on the latest snapshot row;
- average MRR per region = average `mrr_usd` across active snapshot rows;
- churn rate by plan = churned snapshot rows divided by all snapshot rows in that plan;
- top-account revenue = sum invoice `recognized_revenue_usd` by `account_id`, then join the snapshot for current account name and CSAT. This avoids splitting one customer when historical `account_name` values differ.

A production implementation should replace this exercise snapshot with a true subscription-state model/event history.
