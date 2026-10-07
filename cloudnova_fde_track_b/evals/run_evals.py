from pathlib import Path
import duckdb
from app.pipeline import build_clean_dataset, build_account_snapshot
from app.query_agent import QueryPlan, execute

ROOT=Path(__file__).resolve().parents[1]

def main():
    df=build_clean_dataset(ROOT/'data/cloudnova_invoices.csv')
    con=duckdb.connect(); con.register('_df',df); con.execute('CREATE VIEW invoices AS SELECT * FROM _df'); accounts=build_account_snapshot(df); con.register('_accounts',accounts); con.execute('CREATE VIEW accounts AS SELECT * FROM _accounts')
    cases=[
      ('recognized revenue 2024',"SELECT ROUND(SUM(recognized_revenue_usd),2) AS value FROM invoices WHERE EXTRACT(YEAR FROM invoice_date::DATE)=2024",True),
      ('highest average MRR region',"SELECT region, ROUND(AVG(mrr_usd),2) AS avg_mrr_usd FROM accounts WHERE active GROUP BY region ORDER BY avg_mrr_usd DESC LIMIT 1",True),
      ('refunds',"SELECT ROUND(ABS(SUM(CASE WHEN status='refunded' THEN amount_usd ELSE 0 END)),2) AS refund_usd FROM invoices",True),
      ('churn comparison',"SELECT plan, ROUND(AVG(CASE WHEN churned THEN 1.0 ELSE 0.0 END)*100,2) AS churn_rate_pct FROM accounts WHERE plan IN ('enterprise','starter') GROUP BY plan ORDER BY plan",True),
      ('top accounts',"SELECT account_id, account_name, ROUND(SUM(recognized_revenue_usd),2) AS revenue_usd, MAX(csat_score) AS csat_score FROM invoices GROUP BY account_id, account_name ORDER BY revenue_usd DESC LIMIT 5",True),
      ('pending failed',"SELECT COUNT(*) AS invoice_count, ROUND(SUM(amount_usd),2) AS exposed_usd FROM invoices WHERE status IN ('pending','failed')",True),
    ]
    failures=0
    for name,sql,expected in cases:
      try:
        result=execute(con,QueryPlan(sql=sql,explanation='canonical eval query'))
        ok=expected and result.row_count>=1
      except Exception as e:
        ok=False; print(name,'ERROR',e)
      print(('PASS' if ok else 'FAIL'),name)
      failures += not ok
    print(f"{len(cases)-failures}/{len(cases)} evals passed")
    raise SystemExit(1 if failures else 0)

if __name__=='__main__': main()
