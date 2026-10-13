from decimal import Decimal

import pytest

from conftest import txn
from ledger.dedupe import latest_versions
from ledger.feed import read_feed


def test_feed_collapses_to_one_row_per_id(feed_path):
    rows = latest_versions(read_feed(feed_path))
    # 44 batch-1-only + 4 re-synced + 8 new in batch 2
    assert len(rows) == 56
    assert len({r.id for r in rows}) == 56


@pytest.mark.parametrize("txn_id,amount,memo", [
    ("txn_1020", "62.40", "SHELL OIL 57318"),          # $1.00 pending hold -> posted amount
    ("txn_1035", "890.00", "US FOODS 2201"),           # same amount, memo loses PENDING
    ("txn_1041", "1755.00", "SYSCO PHILA 8827"),
    ("txn_1046", "518.35", "RESTAURANT DEPOT 0093"),   # amount changed on posting
])
def test_resynced_ids_keep_the_posted_version(feed_path, txn_id, amount, memo):
    by_id = {r.id: r for r in latest_versions(read_feed(feed_path))}
    assert by_id[txn_id].sync_batch == 2
    assert by_id[txn_id].amount == Decimal(amount)
    assert by_id[txn_id].memo == memo


def test_ids_that_never_resync_keep_their_only_version(feed_path):
    by_id = {r.id: r for r in latest_versions(read_feed(feed_path))}
    assert by_id["txn_1001"].sync_batch == 1


def test_highest_batch_wins_even_when_it_arrives_first():
    newer = txn(sync_batch=3, amount="20.00")
    older = txn(sync_batch=2, amount="19.00")
    assert latest_versions([newer, older]) == [newer]


def test_output_keeps_first_appearance_order():
    a1, b1, a2 = txn(id="a"), txn(id="b"), txn(id="a", sync_batch=2, amount="11.00")
    assert [r.id for r in latest_versions([a1, b1, a2])] == ["a", "b"]
    assert latest_versions([a1, b1, a2])[0].amount == Decimal("11.00")


def test_exact_repeat_in_same_batch_is_harmless():
    t = txn()
    [kept] = latest_versions([t, txn(line=99)])
    assert kept == t and kept.issues == ()


def test_conflicting_versions_in_same_batch_keep_one_line_flagged():
    first, second = txn(amount="10.00", line=2), txn(amount="12.00", line=3)
    [kept] = latest_versions([first, second])
    assert kept.amount == Decimal("12.00")  # later row in the file
    assert kept.issues == ("conflicting versions in sync_batch 1 (lines 2, 3); kept line 3",)


def test_conflict_in_an_older_batch_doesnt_matter_once_a_newer_batch_arrives():
    rows = [txn(amount="10.00"), txn(amount="12.00"), txn(sync_batch=2, amount="11.00")]
    [kept] = latest_versions(rows)
    assert kept.amount == Decimal("11.00") and kept.issues == ()


def test_problems_on_a_superseded_version_are_dropped():
    old_bad = txn(sync_batch=1, amount=None, issues=("amount is not a number: 'x'",))
    new_good = txn(sync_batch=2)
    [kept] = latest_versions([old_bad, new_good])
    assert kept.issues == ()


def test_unreadable_batch_flags_the_id_because_that_version_might_be_newer():
    good = txn(sync_batch=1, line=2)
    unknown = txn(sync_batch=None, amount="99.00", line=3, issues=("sync_batch is not an integer: 'x'",))
    [kept] = latest_versions([good, unknown])
    assert kept.amount == Decimal("10.00")
    assert "line 3 has an unreadable sync_batch" in kept.issues[0]
    assert "sync_batch is not an integer: 'x'" in kept.issues


def test_rows_without_an_id_are_each_kept():
    a = txn(id="", line=5, issues=("id is empty: ''",))
    b = txn(id="", line=9, amount="3.00", issues=("id is empty: ''",))
    assert latest_versions([a, b]) == [a, b]


def test_clean_feed_has_no_issues(feed_path):
    assert all(r.issues == () for r in latest_versions(read_feed(feed_path)))
