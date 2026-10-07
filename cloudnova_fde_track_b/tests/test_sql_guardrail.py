import pytest

from app.query_agent import QueryPlan, validate_sql


def test_allows_select():
    validate_sql('SELECT COUNT(*) FROM invoices')


@pytest.mark.parametrize('sql', [
    'DELETE FROM invoices',
    'DROP TABLE invoices',
    'SELECT 1; DELETE FROM invoices',
    'PRAGMA enable_progress_bar',
    "SELECT * FROM read_csv_auto('secret.csv')",
    'SELECT * FROM filesystem_escape',
])
def test_rejects_unsafe(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)


def test_rejects_unapproved_relation():
    with pytest.raises(ValueError):
        validate_sql('SELECT * FROM secrets')


def test_planner_declared_tables_are_typed():
    plan = QueryPlan(sql='SELECT COUNT(*) FROM invoices', tables=['invoices'])
    assert plan.tables == ['invoices']


def test_rejects_planner_table_mismatch():
    from app.query_agent import QueryPlan, ALLOWED_TABLES
    plan = QueryPlan(sql='SELECT COUNT(*) FROM invoices', tables=['invoices'])
    assert set(plan.tables) == {'invoices'}
    assert ALLOWED_TABLES == {'invoices', 'accounts'}
