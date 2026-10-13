"""Collapse re-synced rows: one transaction id, one row.

Each sync batch is a delta: it re-sends transactions that changed (pending ->
posted) and adds new ones. An id keeps the version from the highest batch it
appears in; ids that never reappear keep their only version.
"""

from typing import Iterable

from ledger.feed import FeedError, Transaction


def latest_versions(transactions: Iterable[Transaction]) -> list[Transaction]:
    """Return one row per id, in order of each id's first appearance in the feed."""
    winners: dict[str, Transaction] = {}
    for txn in transactions:
        current = winners.get(txn.id)
        if current is None or txn.sync_batch > current.sync_batch:
            winners[txn.id] = txn  # dict keeps the id's original insertion position
        elif txn.sync_batch == current.sync_batch and txn != current:
            raise FeedError(
                f"{txn.id} appears twice in sync_batch {txn.sync_batch} with different "
                f"contents (lines {current.line} and {txn.line}); can't tell which is current"
            )
        # A lower batch, or an exact repeat within the same batch, changes nothing.
    return list(winners.values())
