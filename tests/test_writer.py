import csv
from datetime import date
from decimal import Decimal

import pytest

from ledger.classify import LedgerLine
from ledger.writer import format_amount, ledger_row, write_ledger, write_review_notes


def line(**overrides):
    fields = dict(transaction_id="txn_1", date=date(2026, 8, 3), type="purchase",
                  category="Food & beverage", amount=Decimal("1842.17"), reasons=(), line=2)
    fields.update(overrides)
    return LedgerLine(**fields)


@pytest.mark.parametrize("amount,text", [
    (Decimal("1842.17"), "1842.17"),
    (Decimal("-6120.30"), "-6120.30"),
    (Decimal("300"), "300.00"),          # padded to cents
    (Decimal("12.5"), "12.50"),
    (Decimal("10.005"), "10.005"),       # never rounded; the line is already flagged
    (None, ""),                          # unreadable in the feed
])
def test_amount_format(amount, text):
    assert format_amount(amount) == text


def test_row_matches_the_spec_format():
    assert ledger_row(line()) == ["txn_1", "2026-08-03", "purchase", "Food & beverage", "1842.17", "false"]
    assert ledger_row(line(reasons=("x",)))[-1] == "true"


def test_unreadable_values_are_blank():
    assert ledger_row(line(date=None, amount=None, reasons=("bad",))) == \
        ["txn_1", "", "purchase", "Food & beverage", "", "true"]


def test_ledger_file_has_header_and_crlf_like_the_given_example(tmp_path):
    path = tmp_path / "out.csv"
    write_ledger([line()], path)
    assert path.read_bytes() == (b"transaction_id,date,type,category,amount,needs_review\r\n"
                                 b"txn_1,2026-08-03,purchase,Food & beverage,1842.17,false\r\n")


def test_review_notes_have_one_row_per_reason_and_skip_clean_lines(tmp_path):
    path = tmp_path / "notes.csv"
    write_review_notes([
        line(),
        line(transaction_id="txn_2", line=7, reasons=("merchant not on the list", "still pending")),
    ], path)
    with open(path, newline="") as f:
        assert list(csv.reader(f)) == [
            ["transaction_id", "source_line", "reason"],
            ["txn_2", "7", "merchant not on the list"],
            ["txn_2", "7", "still pending"],
        ]
