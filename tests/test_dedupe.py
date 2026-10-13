from decimal import Decimal

import pytest

from conftest import txn
from ledger.dedupe import latest_versions
from ledger.feed import FeedError, read_feed


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
    assert latest_versions([t, txn(line=99)]) == [t]


def test_conflicting_versions_in_same_batch_stop_the_run():
    with pytest.raises(FeedError, match="txn_1 appears twice in sync_batch 1"):
        latest_versions([txn(amount="10.00"), txn(amount="12.00")])
