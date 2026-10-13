"""The whole feed, end to end, against a hand-verified expected ledger.

expected_full.csv was checked row by row against the spec rules, and against
an independent spec-literal derivation that shares no code with ledger/
(all 56 rows agreed). Its first 15 rows are the given expected_first_15.csv.
"""

import csv
import subprocess
import sys

from conftest import FIXTURES, ROOT

EXPECTED = FIXTURES / "expected_full.csv"


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_expected_file_starts_with_the_given_fifteen():
    assert rows(EXPECTED)[:15] == rows(FIXTURES / "expected_first_15.csv")


def test_expected_file_shape():
    expected = rows(EXPECTED)
    assert len(expected) == 56
    assert sorted({r["type"] for r in expected}) == ["deposit", "purchase", "refund", "transfer"]
    assert [r["transaction_id"] for r in expected if r["needs_review"] == "true"] == [
        "txn_1006", "txn_1020", "txn_1028", "txn_1037"]
    assert sorted(r["transaction_id"] for r in expected if r["type"] == "transfer") == [
        "txn_1016", "txn_1017", "txn_1027", "txn_1040", "txn_1051", "txn_1052"]


def test_full_run_matches_expected_line_for_line(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "categorize.py"), str(FIXTURES / "transactions.csv")],
                   cwd=tmp_path, check=True, capture_output=True)
    ours, expected = rows(tmp_path / "ledger_lines.csv"), rows(EXPECTED)
    for got, want in zip(ours, expected):
        assert got == want, f"first mismatch at {want['transaction_id']}"
    assert len(ours) == len(expected)
    assert (tmp_path / "ledger_lines.csv").read_bytes() == EXPECTED.read_bytes()
