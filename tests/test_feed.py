from datetime import date
from decimal import Decimal

import pytest

from ledger.feed import FeedError, parse_rows, read_feed

VALID = dict(id="txn_1", sync_batch="1", date="2026-08-03", account="card",
             merchant="SYSCO", memo="SYSCO", amount="10.00")


def row(**overrides):
    return {**VALID, **overrides}


def test_reads_every_row_of_the_feed(feed_path):
    rows = read_feed(feed_path)
    assert len(rows) == 60
    first = rows[0]
    assert first.id == "txn_1001"
    assert first.sync_batch == 1
    assert first.date == date(2026, 8, 3)
    assert first.account == "card"
    assert first.amount == Decimal("1842.17")


def test_amounts_are_exact_decimals_not_floats(feed_path):
    rows = read_feed(feed_path)
    assert all(isinstance(r.amount, Decimal) for r in rows)
    assert str(rows[0].amount) == "1842.17"  # source precision kept exactly


def test_missing_column_names_the_column(tmp_path):
    path = tmp_path / "feed.csv"
    path.write_text("id,sync_batch,date,account,merchant,amount\n")
    with pytest.raises(FeedError, match="memo"):
        read_feed(path)


def test_whitespace_and_account_case_are_normalized():
    [t] = parse_rows([row(account=" Card ", merchant="  SYSCO 1 ", amount=" -5.00 ")])
    assert t.account == "card"
    assert t.merchant == "SYSCO 1"
    assert t.amount == Decimal("-5.00")


@pytest.mark.parametrize("col,value", [
    ("id", ""),
    ("sync_batch", "two"),
    ("date", "08/03/2026"),
    ("account", "savings"),
    ("amount", "12,00"),
    ("amount", "NaN"),
])
def test_bad_values_stop_the_run_with_line_number(col, value):
    rows = [row(), row(**{col: value})]
    with pytest.raises(FeedError, match=rf"line 3: {col}"):
        parse_rows(rows)
