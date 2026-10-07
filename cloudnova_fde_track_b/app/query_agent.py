from __future__ import annotations

import json
import re
from dataclasses import dataclass

try:
    import duckdb
except ImportError:  # Allows SQL guardrail tests without the optional runtime dependency.
    duckdb = None
from pydantic import BaseModel, Field

from .config import settings

class QueryPlan(BaseModel):
    sql: str = Field(min_length=1)
    explanation: str = Field(default="")

@dataclass
class QueryResult:
    answer: list[dict]
    sql: str
    explanation: str
    row_count: int

SYSTEM_PROMPT = """You are the CloudNova analytics query planner. Generate ONLY read-only SQL over the DuckDB view `invoices`. The governed view contains cleaned fields including amount_usd, recognized_revenue_usd, mrr_usd, status, plan, region, account_id, account_name, churned, csat_score and invoice_date. Never calculate financial values in prose. Use SQL aggregation. Return JSON with keys sql and explanation. SQL must be one SELECT statement and must not reference any table except invoices."""


def validate_sql(sql: str) -> None:
    s = sql.strip().rstrip(";").strip()
    if ";" in s: raise ValueError("Multiple SQL statements are not allowed")
    if not re.match(r"^select\b", s, flags=re.I): raise ValueError("Only SELECT statements are allowed")
    if not re.search(r"\b(invoices|accounts)\b", s, flags=re.I): raise ValueError("Query must use a governed view")
    if re.search(r"\b(from|join)\s+(?!invoices\b|accounts\b)[A-Za-z_]", s, flags=re.I): raise ValueError("Query references an unapproved relation")
    forbidden = r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma|export|install|load)\b"
    if re.search(forbidden, s, flags=re.I): raise ValueError("Forbidden SQL operation")


def plan_with_llm(question: str) -> QueryPlan:
    if not settings.api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    from openai import OpenAI
    kwargs = {"api_key": settings.api_key}
    if settings.base_url: kwargs["base_url"] = settings.base_url
    client = OpenAI(**kwargs)
    response = client.chat.completions.create(
        model=settings.model,
        temperature=0,
        response_format={"type":"json_object"},
        messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":question}],
    )
    return QueryPlan.model_validate_json(response.choices[0].message.content)


def execute(con: duckdb.DuckDBPyConnection, plan: QueryPlan) -> QueryResult:
    validate_sql(plan.sql)
    sql = plan.sql.strip().rstrip(";")
    rows = con.execute(sql).fetchdf().to_dict(orient="records")
    return QueryResult(rows, sql, plan.explanation, len(rows))
