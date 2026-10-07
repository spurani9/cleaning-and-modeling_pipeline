from __future__ import annotations

import argparse
import json

import duckdb

from .config import settings
from .pipeline import build_account_snapshot, build_clean_dataset
from .query_agent import execute, plan_with_llm

DEMO_QUESTIONS = [
    "What was our total recognized revenue in USD for paid invoices in 2024?",
    "Which region has the highest average MRR per account?",
    "How much have we given back in refunds?",
    "What's the churn rate among Enterprise accounts vs Starter?",
    "List the top 5 accounts by revenue, and flag any with CSAT <= 2.",
    "How many invoices are stuck in pending/failed and what's the exposed $?",
]


def prepare() -> tuple[duckdb.DuckDBPyConnection, object]:
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    out = settings.artifact_dir / "cleaned_invoices.csv"
    df = build_clean_dataset(settings.raw_csv, out)
    con = duckdb.connect()
    con.register("_df", df)
    con.execute("CREATE OR REPLACE VIEW invoices AS SELECT * FROM _df")
    accounts = build_account_snapshot(df)
    con.register("_accounts", accounts)
    con.execute("CREATE OR REPLACE VIEW accounts AS SELECT * FROM _accounts")
    return con, df


def ask(con: duckdb.DuckDBPyConnection, question: str) -> None:
    plan = plan_with_llm(question)
    result = execute(con, plan)
    print(json.dumps({
        "question": question,
        "answer": result.answer,
        "sql": result.sql,
        "explanation": result.explanation,
        "assumptions": result.assumptions,
        "row_count": result.row_count,
    }, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="CloudNova Track B demo")
    parser.add_argument("question", nargs="*", help="Natural-language stakeholder question")
    parser.add_argument("--demo", action="store_true", help="Run all six stakeholder questions through the live model")
    args = parser.parse_args()

    con, df = prepare()
    print(f"Loaded {len(df):,} governed invoice records")

    if args.demo:
        for question in DEMO_QUESTIONS:
            ask(con, question)
        return

    if not args.question:
        print("Run with a stakeholder question or --demo. Example:")
        print('  python -m app "What was our total recognized revenue in USD for paid invoices in 2024?"')
        return

    ask(con, " ".join(args.question))


if __name__ == "__main__":
    main()
