from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

PLAN = {"starter":"starter","start":"starter","tier 1":"starter","pro":"pro","professional":"pro","tier 2":"pro","enterprise":"enterprise","ent":"enterprise","tier 3":"enterprise"}
STATUS = {"paid":"paid","complete":"paid","completed":"paid","success":"paid","pending":"pending","in_review":"pending","awaiting":"pending","failed":"failed","declined":"failed","error":"failed","refunded":"refunded","refund":"refunded","charged_back":"refunded","void":"void","cancelled":"void","canceled":"void"}
CYCLE = {"monthly":"monthly","annual":"annual","annually":"annual","yearly":"annual"}
PAYMENT = {"credit card":"credit_card","credit_card":"credit_card","ach":"ach","wire":"wire","wire transfer":"wire","invoice":"invoice"}
BOOL = {"true":True,"yes":True,"1":True,"y":True,"false":False,"no":False,"0":False,"n":False}
FX = {"USD": Decimal("1"), "EUR": Decimal("1.08"), "GBP": Decimal("1.27")}
PRICE = {"starter": Decimal("49"), "pro": Decimal("99"), "enterprise": Decimal("299")}
STATUS_PRECEDENCE = {"paid":5,"refunded":4,"pending":3,"failed":2,"void":1}


def norm(value: object) -> str:
    return str(value).strip().lower()


def parse_amount(value: object) -> Decimal:
    s = str(value).strip().replace(",", "")
    s = re.sub(r"[$€£]", "", s)
    s = re.sub(r"\s*(USD|EUR|GBP)\s*$", "", s, flags=re.I)
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {value!r}") from exc


def parse_date(value: object) -> tuple[pd.Timestamp, bool]:
    s = str(value).strip()
    # Explicit month-name and ISO dates are unambiguous.
    if re.search(r"[A-Za-z]", s) or re.match(r"^\d{4}[-/]", s):
        return pd.to_datetime(s, errors="raise"), False
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", s)
    if not m:
        raise ValueError(f"Unsupported date: {value!r}")
    a,b,y = map(int,m.groups())
    # Dataset convention: numeric slash/dash values are treated MM/DD/YYYY
    # unless the first component proves it cannot be a month.
    ambiguous = a <= 12 and b <= 12
    if a > 12:
        day, month = a, b
    else:
        month, day = a, b
    return pd.Timestamp(year=y, month=month, day=day), ambiguous


def normalize_email(value: object) -> str | None:
    if pd.isna(value) or not str(value).strip():
        return None
    s = str(value).strip().replace("_at_", "@")
    if s.count("@") != 1 or " " in s or "." not in s.split("@",1)[1]:
        return None
    return s.lower()


def build_account_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Build one current-state row per account from the latest observed invoice.

    This is an exercise-level snapshot because the source has no subscription event history.
    It prevents invoice repetition from inflating account-level MRR/churn metrics.
    """
    work = df.copy()
    work["_invoice_dt"] = pd.to_datetime(work["invoice_date"])
    work = work.sort_values(["account_id", "_invoice_dt", "invoice_id"], kind="stable")
    latest = work.drop_duplicates("account_id", keep="last").copy()
    latest["active"] = ~latest["churned"]
    latest["mrr_usd"] = latest["mrr_usd"].where(latest["active"], 0.0)
    return latest[["account_id","account_name","region","industry","plan","churned","active","mrr_usd","csat_score","invoice_date"]]


def build_clean_dataset(raw_csv: str | Path, output_csv: str | Path | None = None) -> pd.DataFrame:
    df = pd.read_csv(raw_csv, dtype=str, keep_default_na=True)
    original_rows = len(df)
    df["_source_order"] = range(len(df))

    # Exact duplicates first.
    df = df.drop_duplicates(keep="first").copy()
    df["dedup_reason"] = "unique_invoice_id"
    exact_removed = original_rows - len(df)

    # Normalize fields needed for deterministic duplicate resolution.
    df["status"] = df["status"].map(lambda x: STATUS.get(norm(x)))
    df["plan"] = df["plan"].map(lambda x: PLAN.get(norm(x)))
    df["billing_cycle"] = df["billing_cycle"].map(lambda x: CYCLE.get(norm(x)))
    df["payment_method"] = df["payment_method"].map(lambda x: PAYMENT.get(norm(x)) if pd.notna(x) else None)
    if df[["status","plan","billing_cycle"]].isna().any().any():
        raise ValueError("Unknown categorical value encountered during normalization")

    df["_precedence"] = df["status"].map(STATUS_PRECEDENCE)
    df = df.sort_values(["invoice_id","_precedence","_source_order"], ascending=[True,False,True], kind="stable")
    duplicate_ids = set(df.loc[df.duplicated("invoice_id", keep=False), "invoice_id"])
    conflicting_ids = {
        iid for iid, group in df.groupby("invoice_id")
        if iid in duplicate_ids and group["status"].nunique(dropna=False) > 1
    }
    winners = df.drop_duplicates("invoice_id", keep="first").copy()
    winners["dedup_reason"] = winners.apply(
        lambda r: (f"conflicting_invoice_id_resolved:{r.status}" if r.invoice_id in conflicting_ids
                   else "normalized_duplicate_resolved" if r.invoice_id in duplicate_ids
                   else r.dedup_reason),
        axis=1,
    )
    df = winners.drop(columns=["_precedence"])

    df["contact_email"] = df["contact_email"].map(normalize_email)
    df["region"] = df["region"].map(lambda x: str(x).strip().upper() if pd.notna(x) else None)
    df["industry"] = df["industry"].map(lambda x: str(x).strip() if pd.notna(x) else None)
    df["currency"] = df["currency"].str.strip().str.upper()
    if not df["currency"].isin(FX).all(): raise ValueError("Unsupported currency")
    df["amount_local"] = df["amount"].map(parse_amount).astype(float)
    df["amount_usd"] = [float(Decimal(str(a)) * FX[c]) for a,c in zip(df["amount_local"],df["currency"])]
    df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="raise").astype(float)
    if not df["discount_pct"].between(0, 100).all():
        raise ValueError("discount_pct must be between 0 and 100")
    df["seats"] = pd.to_numeric(df["seats"], errors="raise").astype(int)
    if not df["seats"].gt(0).all():
        raise ValueError("seats must be positive")
    df["csat_score"] = pd.to_numeric(df["csat_score"], errors="coerce")
    if not df["csat_score"].dropna().between(1, 5).all():
        raise ValueError("csat_score must be between 1 and 5 when present")
    df["support_tickets"] = pd.to_numeric(df["support_tickets"], errors="raise").astype(int)
    if not df["support_tickets"].ge(0).all():
        raise ValueError("support_tickets must be non-negative")
    df["churned"] = df["churned"].map(lambda x: BOOL.get(norm(x)))
    if df["churned"].isna().any(): raise ValueError("Unknown boolean value")

    for col in ["signup_date","invoice_date"]:
        parsed = df[col].map(parse_date)
        df[col] = parsed.map(lambda x: x[0].date().isoformat())
        if col == "invoice_date": df["date_parse_warning"] = parsed.map(lambda x: x[1])

    df["mrr_usd"] = [float(PRICE[p] * Decimal(str(s)) * (Decimal("1") - Decimal(str(d))/Decimal("100"))) for p,s,d in zip(df["plan"],df["seats"],df["discount_pct"])]
    df["recognized_revenue_usd"] = df.apply(lambda r: r["amount_usd"] if r["status"] in {"paid","refunded"} else 0.0, axis=1)
    df = df.drop(columns=["amount","_source_order"])
    if df["invoice_id"].duplicated().any(): raise AssertionError("invoice_id must be unique after dedup")
    if output_csv:
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv, index=False)
    return df
