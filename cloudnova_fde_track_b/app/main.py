from __future__ import annotations

import argparse
import json
import duckdb

from .config import settings
from .pipeline import build_clean_dataset, build_account_snapshot
from .query_agent import plan_with_llm, execute


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


def main() -> None:
    parser = argparse.ArgumentParser(description="CloudNova Track B demo")
    parser.add_argument("question", nargs="*", help="Natural-language stakeholder question")
    args = parser.parse_args()
    con, df = prepare()
    print(f"Loaded {len(df):,} governed invoice records")
    if not args.question:
        print("Run with a stakeholder question, e.g. python -m app 'What was our total recognized revenue in USD for paid invoices in 2024?'")
        return
    question = " ".join(args.question)
    plan = plan_with_llm(question)
    result = execute(con, plan)
    print(json.dumps({"answer":result.answer,"sql":result.sql,"explanation":result.explanation,"row_count":result.row_count}, indent=2, default=str))

if __name__ == "__main__": main()
