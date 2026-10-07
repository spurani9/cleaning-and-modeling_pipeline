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


def test_account_snapshot_is_one_row_per_account():
    from app.pipeline import build_account_snapshot
    df = build_clean_dataset(ROOT / 'data/cloudnova_invoices.csv')
    accounts = build_account_snapshot(df)
    assert accounts.account_id.is_unique
    assert len(accounts) == 3815


def test_financial_fields_are_governed():
    df = build_clean_dataset(ROOT / 'data/cloudnova_invoices.csv')
    assert df.discount_pct.between(0, 100).all()
    assert df.seats.gt(0).all()
    assert df.csat_score.dropna().between(1, 5).all()
    assert df.support_tickets.ge(0).all()
