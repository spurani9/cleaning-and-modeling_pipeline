from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

try:
    import duckdb
except ImportError:  # pragma: no cover - dependency is required for runtime.
    duckdb = None
from pydantic import BaseModel, Field, field_validator

from .config import settings


ALLOWED_TABLES = {"invoices", "accounts"}
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma|export|install|load|call|execute|replace|vacuum|checkpoint|use)\b",
    re.I,
)
FORBIDDEN_FUNCTIONS = re.compile(
    r"\b(read_csv|read_csv_auto|read_parquet|read_json|glob|httpfs|http_get|http_post|sqlite_scan|postgres_scan|mysql_scan|parquet_scan|csv_scan)\s*\(",
    re.I,
)
TABLE_PATTERN = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.I)

# The LLM may use SQL syntax, but it should only see this governed semantic surface.
SCHEMA = {
    "invoices": {
        "invoice_id": "string",
        "account_id": "string",
        "account_name": "string",
        "region": "string",
        "industry": "string|null",
        "plan": "starter|pro|enterprise",
        "billing_cycle": "monthly|annual",
        "seats": "integer",
        "currency": "USD|EUR|GBP",
        "amount_local": "decimal",
        "amount_usd": "decimal",
        "discount_pct": "decimal",
        "status": "paid|pending|failed|refunded|void",
        "payment_method": "credit_card|ach|wire|invoice|null",
        "signup_date": "date",
        "invoice_date": "date",
        "churned": "boolean",
        "csat_score": "decimal|null",
        "support_tickets": "integer",
        "mrr_usd": "decimal",
        "recognized_revenue_usd": "decimal",
        "dedup_reason": "string",
        "date_parse_warning": "boolean",
    },
    "accounts": {
        "account_id": "string",
        "account_name": "string",
        "region": "string",
        "industry": "string|null",
        "plan": "starter|pro|enterprise",
        "churned": "boolean",
        "active": "boolean",
        "mrr_usd": "decimal",
        "csat_score": "decimal|null",
        "invoice_date": "date",
    },
}


class QueryIntent(str, Enum):
    revenue = "revenue"
    mrr = "mrr"
    churn = "churn"
    refunds = "refunds"
    exposure = "exposure"
    account_revenue = "account_revenue"
    other = "other"


class QueryPlan(BaseModel):
    intent: QueryIntent = QueryIntent.other
    sql: str = Field(min_length=1)
    tables: list[str] = Field(default_factory=list)
    explanation: str = Field(default="")
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("tables")
    @classmethod
    def valid_tables(cls, values: list[str]) -> list[str]:
        normalized = [v.strip().lower() for v in values]
        unknown = set(normalized) - ALLOWED_TABLES
        if unknown:
            raise ValueError(f"Unknown governed table(s): {sorted(unknown)}")
        return sorted(set(normalized))


@dataclass
class QueryResult:
    answer: list[dict]
    sql: str
    explanation: str
    assumptions: list[str]
    row_count: int


SYSTEM_PROMPT = f"""You are the CloudNova analytics query planner.

Your job is ONLY to translate a user's natural-language analytics question into one safe, read-only DuckDB query over the governed semantic layer. Do not calculate financial answers in prose.

Return JSON matching this schema:
{{
  "intent": "revenue|mrr|churn|refunds|exposure|account_revenue|other",
  "sql": "SELECT ...",
  "tables": ["invoices" or "accounts"],
  "explanation": "short explanation",
  "assumptions": ["only material assumptions"]
}}

Governed tables and columns:
{SCHEMA}

Business rules:
- Recognized revenue = amount_usd for status='paid' OR status='refunded'; pending/failed/void are zero.
- For a question explicitly asking for "paid invoices", filter status='paid' and do not include refunded rows.
- Refund amount is the positive absolute value of negative refunded amount_usd.
- MRR = mrr_usd already derived by the deterministic pipeline; never recompute it from invoice amount.
- accounts is one latest-observed-invoice snapshot per account. Use it for account-level MRR, churn and latest CSAT.
- Only active accounts (active=true) have MRR for the region-average MRR question.
- Churn rate = churned accounts / all accounts in the requested plan, using accounts.
- Top-account revenue = SUM(recognized_revenue_usd) by account; join accounts only when current account attributes such as latest CSAT are needed.
- Pending/failed exposure = count of normalized pending/failed invoices and SUM(amount_usd) for those rows.
- Fixed FX has already been applied to amount_usd: USD=1.0, EUR=1.08, GBP=1.27.
- Never divide annual invoice amounts by 12 for recognized revenue.

Safety:
- Exactly one SELECT statement. Keep the query simple and auditable; CTEs are intentionally not required by the demo contract.
- Only reference invoices and/or accounts.
- No filesystem, network, extension, pragma, mutation or administrative functions.
- Do not invent tables or columns.
"""


def _normalize_sql(sql: str) -> str:
    return sql.strip().rstrip(";").strip()


def validate_sql(sql: str) -> None:
    s = _normalize_sql(sql)
    if not s:
        raise ValueError("SQL is empty")
    if ";" in s:
        raise ValueError("Multiple SQL statements are not allowed")
    if not re.match(r"^select\b", s, flags=re.I):
        raise ValueError("Only SELECT statements are allowed")
    if FORBIDDEN_SQL.search(s):
        raise ValueError("Forbidden SQL operation")
    if FORBIDDEN_FUNCTIONS.search(s):
        raise ValueError("Filesystem/network SQL functions are not allowed")

    relations = {m.group(1).lower() for m in TABLE_PATTERN.finditer(s)}
    # SQL also uses `FROM` inside expressions such as `EXTRACT(YEAR FROM invoice_date)`.
    # Treat governed schema columns as expression identifiers, not relations. This keeps
    # the static guardrail strict for real table references without rejecting valid SQL.
    schema_columns = {column for table in SCHEMA.values() for column in table}
    relation_candidates = relations - schema_columns
    if not relation_candidates:
        relation_candidates = relations & ALLOWED_TABLES
    if not relation_candidates:
        raise ValueError("Query must reference a governed relation")
    unknown = relation_candidates - ALLOWED_TABLES
    if unknown:
        raise ValueError(f"Query references unapproved relation(s): {sorted(unknown)}")

    # Block common DuckDB escape hatches even when expressed as function-like syntax.
    if re.search(r"\b(secret|current_setting|set_config|read_blob|read_text)\s*\(", s, re.I):
        raise ValueError("Potential environment/filesystem access is not allowed")


def validate_against_connection(con, sql: str) -> None:
    """Ask DuckDB to plan the query without executing it.

    This catches unknown columns, invalid casts and malformed SQL after the static
    safety checks have passed.
    """
    validate_sql(sql)
    con.execute(f"EXPLAIN {_normalize_sql(sql)}")


def plan_with_llm(question: str) -> QueryPlan:
    if not question.strip():
        raise ValueError("Question must not be empty")
    if not settings.api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    from openai import OpenAI

    kwargs = {"api_key": settings.api_key}
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    client = OpenAI(**kwargs)
    response = client.chat.completions.create(
        model=settings.model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}],
    )
    plan = QueryPlan.model_validate_json(response.choices[0].message.content)
    validate_sql(plan.sql)
    sql_tables = {m.group(1).lower() for m in TABLE_PATTERN.finditer(plan.sql)}
    if set(plan.tables) != sql_tables:
        raise ValueError("Planner-declared tables do not match tables referenced by SQL")
    return plan


def execute(con, plan: QueryPlan) -> QueryResult:
    validate_against_connection(con, plan.sql)
    sql = _normalize_sql(plan.sql)
    rows = con.execute(sql).fetchdf().to_dict(orient="records")
    return QueryResult(rows, sql, plan.explanation, plan.assumptions, len(rows))
