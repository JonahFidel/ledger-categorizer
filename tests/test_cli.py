import csv
import subprocess
import sys

from conftest import FIXTURES, ROOT

SCRIPT = ROOT / "categorize.py"


def run(*args, cwd):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          cwd=cwd, capture_output=True, text=True)


def test_one_command_writes_both_files_to_the_current_directory(tmp_path):
    result = run(FIXTURES / "transactions.csv", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "56 ledger lines written to ledger_lines.csv; 4 need review" in result.stdout
    assert (tmp_path / "ledger_lines.csv").exists()
    assert (tmp_path / "review_notes.csv").exists()


def test_first_fifteen_lines_are_byte_identical_to_the_given_example(tmp_path):
    run(FIXTURES / "transactions.csv", cwd=tmp_path)
    ours = (tmp_path / "ledger_lines.csv").read_bytes().splitlines(keepends=True)
    given = (FIXTURES / "expected_first_15.csv").read_bytes().splitlines(keepends=True)
    assert ours[:16] == given


def test_review_notes_explain_every_flagged_line(tmp_path):
    run(FIXTURES / "transactions.csv", cwd=tmp_path)
    with open(tmp_path / "ledger_lines.csv", newline="") as f:
        flagged = {r["transaction_id"] for r in csv.DictReader(f) if r["needs_review"] == "true"}
    with open(tmp_path / "review_notes.csv", newline="") as f:
        notes = list(csv.DictReader(f))
    assert {n["transaction_id"] for n in notes} == flagged == {"txn_1006", "txn_1020", "txn_1028", "txn_1037"}


def test_output_paths_can_be_chosen(tmp_path):
    result = run(FIXTURES / "transactions.csv", "-o", tmp_path / "a.csv", "--notes", tmp_path / "b.csv",
                 cwd=tmp_path)
    assert result.returncode == 0
    assert (tmp_path / "a.csv").exists() and (tmp_path / "b.csv").exists()


def test_bad_rows_still_produce_a_ledger_and_exit_zero(tmp_path):
    feed = tmp_path / "feed.csv"
    feed.write_text("id,sync_batch,date,account,merchant,memo,amount\n"
                    "t1,1,2026-08-03,card,SYSCO 1,SYSCO 1,10.00\n"
                    "t2,1,someday,card,SYSCO 1,SYSCO 1,lots\n")
    result = run(feed, cwd=tmp_path)
    assert result.returncode == 0
    assert (tmp_path / "ledger_lines.csv").read_text().splitlines()[2] == "t2,,purchase,Food & beverage,,true"


def test_missing_feed_is_a_clear_error(tmp_path):
    result = run(tmp_path / "nope.csv", cwd=tmp_path)
    assert result.returncode == 1
    assert "file not found" in result.stderr and "nope.csv" in result.stderr
    assert not (tmp_path / "ledger_lines.csv").exists()


def test_missing_column_is_a_clear_error(tmp_path):
    feed = tmp_path / "feed.csv"
    feed.write_text("id,sync_batch,date,account,merchant,memo\n")
    result = run(feed, cwd=tmp_path)
    assert result.returncode == 1
    assert "missing column(s): amount" in result.stderr


def test_broken_operator_settings_are_a_clear_error(tmp_path):
    bad = tmp_path / "operator.toml"
    bad.write_text("[transfers]\nkeywords = ['PAYMENT']\n")
    result = run(FIXTURES / "transactions.csv", "--operator", bad, cwd=tmp_path)
    assert result.returncode == 1
    assert "invalid operator settings" in result.stderr
