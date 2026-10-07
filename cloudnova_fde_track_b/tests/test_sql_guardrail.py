import pytest
from app.query_agent import validate_sql

def test_allows_select(): validate_sql('SELECT COUNT(*) FROM invoices')
@pytest.mark.parametrize('sql',['DELETE FROM invoices','DROP TABLE invoices','SELECT 1; DELETE FROM invoices','PRAGMA enable_progress_bar'])
def test_rejects_unsafe(sql):
    with pytest.raises(ValueError): validate_sql(sql)
