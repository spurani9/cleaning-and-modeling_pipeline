from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import duckdb
import pandas as pd

from app.pipeline import build_account_snapshot, build_clean_dataset
from app.query_agent import QueryPlan, execute

ROOT = Path(__file__).resolve().parents[1]


def _connection():
    df = build_clean_dataset(ROOT / "data/cloudnova_invoices.csv")
    accounts = build_account_snapshot(df)
    con = duckdb.connect()
    con.register("_df", df)
    con.execute("CREATE VIEW invoices AS SELECT * FROM _df")
    con.register("_accounts", accounts)
    con.execute("CREATE VIEW accounts AS SELECT * FROM _accounts")
    return con, df, accounts


def _rows(result):
    return pd.DataFrame(result.answer)


def main() -> None:
    con, df, accounts = _connection()
    cases = [
        {
            "name": "1. paid recognized revenue in 2024",
            "sql": "SELECT ROUND(SUM(amount_usd), 2) AS revenue_usd FROM invoices WHERE status='paid' AND EXTRACT(YEAR FROM invoice_date::DATE)=2024",
            "expected": {"revenue_usd": 32686371.05},
        },
        {
            "name": "2. highest average MRR region",
            "sql": "SELECT region, ROUND(AVG(mrr_usd), 2) AS avg_mrr_usd FROM accounts WHERE active GROUP BY region ORDER BY avg_mrr_usd DESC LIMIT 1",
            "expected": {"region": "APAC", "avg_mrr_usd": 6154.42},
        },
        {
            "name": "3. refunds",
            "sql": "SELECT ROUND(ABS(SUM(amount_usd)), 2) AS refund_usd FROM invoices WHERE status='refunded'",
            "expected": {"refund_usd": 8893303.77},
        },
        {
            "name": "4. Enterprise vs Starter churn",
            "sql": "SELECT plan, ROUND(AVG(CASE WHEN churned THEN 1.0 ELSE 0.0 END)*100, 2) AS churn_rate_pct FROM accounts WHERE plan IN ('enterprise','starter') GROUP BY plan ORDER BY plan",
            "expected": [
                {"plan": "enterprise", "churn_rate_pct": 21.92},
                {"plan": "starter", "churn_rate_pct": 18.83},
            ],
        },
        {
            "name": "5. top 5 accounts by recognized revenue + latest CSAT",
            "sql": "SELECT r.account_id, a.account_name, ROUND(r.revenue_usd, 2) AS revenue_usd, a.csat_score, CASE WHEN a.csat_score <= 2 THEN true ELSE false END AS low_csat_flag FROM (SELECT account_id, SUM(recognized_revenue_usd) AS revenue_usd FROM invoices GROUP BY account_id) r JOIN accounts a USING(account_id) ORDER BY revenue_usd DESC, r.account_id LIMIT 5",
            "expected": [
                {"account_id":"ACC-7509","account_name":"Stark Inc","revenue_usd":1210592.75,"csat_score":4.0,"low_csat_flag":False},
                {"account_id":"ACC-1420","account_name":"Tyrell Industries","revenue_usd":1208092.75,"csat_score":None,"low_csat_flag":False},
                {"account_id":"ACC-9946","account_name":"Initech LLC","revenue_usd":1205642.75,"csat_score":4.0,"low_csat_flag":False},
                {"account_id":"ACC-1196","account_name":"Pied Piper Partners","revenue_usd":1107352.84,"csat_score":3.0,"low_csat_flag":False},
                {"account_id":"ACC-5211","account_name":"Oscorp Industries","revenue_usd":1085078.48,"csat_score":5.0,"low_csat_flag":False},
            ],
        },
        {
            "name": "6. pending/failed exposure",
            "sql": "SELECT COUNT(*) AS invoice_count, ROUND(SUM(amount_usd), 2) AS exposed_usd FROM invoices WHERE status IN ('pending','failed')",
            "expected": {"invoice_count": 894, "exposed_usd": 28983255.81},
        },
    ]

    # Required rubric case: this is intentionally unsupported by the supplied data.
    # There is no subscription-state event history, so historical pre-churn MRR
    # cannot be answered without inventing facts. This is an expected failure,
    # not a deterministic SQL correctness failure.
    expected_unsupported = {
        "name": "EXPECTED FAIL — historical pre-churn MRR",
        "question": "What was each account's MRR immediately before it churned?",
        "reason": "The ledger has current churned state but no subscription-state event history.",
    }

    def _normalize_value(value):
        # DuckDB/pandas represent SQL NULLs as NaN in some dataframe paths.
        return None if pd.isna(value) else value

    def _normalize_rows(rows):
        normalized = []
        for row in rows:
            normalized.append({k: _normalize_value(v) for k, v in row.items()})
        return normalized

    failures = 0
    for case in cases:
        try:
            result = execute(con, QueryPlan(sql=case["sql"], explanation="canonical eval query"))
            actual = _normalize_rows(_rows(result).to_dict(orient="records"))
            expected = case["expected"]
            if isinstance(expected, dict):
                ok = len(actual) == 1 and all(
                    (pd.isna(actual[0].get(k)) and v is None) or actual[0].get(k) == v
                    for k, v in expected.items()
                )
            else:
                ok = actual == expected
            print(f"{'PASS' if ok else 'FAIL'} {case['name']}")
            if not ok:
                print("  expected:", expected)
                print("  actual:  ", actual)
                failures += 1
        except Exception as exc:
            print(f"FAIL {case['name']}: {exc}")
            failures += 1

    print(f"{len(cases) - failures}/{len(cases)} deterministic stakeholder evals passed")
    print(f"EXPECTED FAIL {expected_unsupported['name']}: {expected_unsupported['reason']}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
