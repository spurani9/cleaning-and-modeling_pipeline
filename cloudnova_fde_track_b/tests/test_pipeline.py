from pathlib import Path
from app.pipeline import build_clean_dataset

ROOT=Path(__file__).resolve().parents[1]

def test_pipeline_contract():
    df=build_clean_dataset(ROOT/'data/cloudnova_invoices.csv')
    assert len(df)==5000
    assert df.invoice_id.is_unique
    assert set(df.status.unique()) <= {'paid','pending','failed','refunded','void'}
    assert set(df.plan.unique()) <= {'starter','pro','enterprise'}
    assert set(df.billing_cycle.unique()) <= {'monthly','annual'}
    assert df.amount_usd.notna().all()
    assert df.mrr_usd.ge(0).all()
