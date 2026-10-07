from __future__ import annotations

import argparse
from pathlib import Path
import json
import math

import duckdb
import pandas as pd

from app.pipeline import build_account_snapshot, build_clean_dataset
from app.query_agent import execute, plan_with_llm

ROOT = Path(__file__).resolve().parents[1]

CASES = [
    ("revenue_2024", "What was our total recognized revenue in USD for paid invoices in 2024?", [{"revenue_usd": 32686371.05}]),
    ("region_mrr", "Which region has the highest average MRR per account?", [{"region": "APAC", "avg_mrr_usd": 6154.42}]),
    ("refunds", "How much have we given back in refunds?", [{"refund_usd": 8893303.77}]),
    ("churn", "What's the churn rate among Enterprise accounts vs Starter?", [{"plan": "enterprise", "churn_rate_pct": 21.92}, {"plan": "starter", "churn_rate_pct": 18.83}]),
    ("top_accounts", "List the top 5 accounts by revenue, and flag any with CSAT <= 2.", [
        {"account_id":"ACC-1420","account_name":"Tyrell Industries","revenue_usd":1205642.75,"csat_score":None,"low_csat_flag":False},
        {"account_id":"ACC-7509","account_name":"Stark Inc","revenue_usd":1205642.75,"csat_score":4.0,"low_csat_flag":False},
        {"account_id":"ACC-9946","account_name":"Initech LLC","revenue_usd":1205642.75,"csat_score":4.0,"low_csat_flag":False},
        {"account_id":"ACC-5211","account_name":"Oscorp Industries","revenue_usd":1085078.48,"csat_score":5.0,"low_csat_flag":False},
        {"account_id":"ACC-1196","account_name":"Pied Piper Partners","revenue_usd":1085077.84,"csat_score":3.0,"low_csat_flag":False},
    ]),
    ("exposure", "How many invoices are stuck in pending/failed and what's the exposed $?", [{"invoice_count": 894, "exposed_usd": 28983255.81}]),
]


def make_connection():
    df = build_clean_dataset(ROOT / "data/cloudnova_invoices.csv")
    accounts = build_account_snapshot(df)
    con = duckdb.connect()
    con.register("_df", df)
    con.execute("CREATE VIEW invoices AS SELECT * FROM _df")
    con.register("_accounts", accounts)
    con.execute("CREATE VIEW accounts AS SELECT * FROM _accounts")
    return con


def normalize(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, float):
        return round(value, 2)
    return value


def rows_equivalent(actual, expected):
    if len(actual) != len(expected):
        return False
    for a, e in zip(actual, expected):
        if set(a) != set(e):
            return False
        for key in e:
            av, ev = normalize(a[key]), normalize(e[key])
            if av != ev:
                return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=len(CASES))
    args = parser.parse_args()

    con = make_connection()
    failures = 0
    for name, question, expected in CASES[:args.limit]:
        try:
            plan = plan_with_llm(question)
            result = execute(con, plan)
            ok = rows_equivalent(result.answer, expected)
            print(f"{'PASS' if ok else 'FAIL'} {name}")
            print("  SQL:", result.sql)
            if not ok:
                print("  expected:", json.dumps(expected, default=str))
                print("  actual:  ", json.dumps(result.answer, default=str))
                failures += 1
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            failures += 1

    print(f"{len(CASES[:args.limit]) - failures}/{len(CASES[:args.limit])} live-model evals passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
