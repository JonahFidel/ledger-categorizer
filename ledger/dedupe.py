"""Collapse re-synced rows: one transaction id, one row.

Each sync batch is a delta: it re-sends transactions that changed (pending ->
posted) and adds new ones. An id keeps the version from the highest batch it
appears in; ids that never reappear keep their only version.

Anything ambiguous is flagged for review on the surviving row instead of
stopping the run:
- two different versions of an id in the same batch (the later row is kept);
- a version whose batch number is unreadable (we can't know if it was newer).
A row with no id can't be matched to anything, so it is kept on its own.
"""

from dataclasses import replace
from typing import Iterable

from ledger.feed import Transaction


def latest_versions(transactions: Iterable[Transaction]) -> list[Transaction]:
    """Return one row per id, in order of each id's first appearance in the feed."""
    groups: dict[str, list[Transaction]] = {}
    for txn in transactions:
        key = txn.id or f"<no id, line {txn.line}>"
        groups.setdefault(key, []).append(txn)  # dict keeps first-appearance order
    return [_pick(versions) for versions in groups.values()]


def _pick(versions: list[Transaction]) -> Transaction:
    known = [v for v in versions if v.sync_batch is not None]
    unknown = [v for v in versions if v.sync_batch is None]

    if not known:
        winner, issues = versions[-1], list(versions[-1].issues)
    else:
        top = max(v.sync_batch for v in known)
        at_top = [v for v in known if v.sync_batch == top]
        winner = at_top[-1]
        issues = [i for v in at_top for i in v.issues]
        if len(set(at_top)) > 1:  # set() collapses exact repeats, which are harmless
            lines = ", ".join(str(v.line) for v in at_top)
            issues.append(
                f"conflicting versions in sync_batch {top} (lines {lines}); "
                f"kept line {winner.line}"
            )

    for v in unknown:
        if v is not winner:
            issues.append(
                f"another version on line {v.line} has an unreadable sync_batch; "
                "it may be newer"
            )
            issues.extend(v.issues)

    return replace(winner, issues=tuple(dict.fromkeys(issues)))  # dedupe, keep order
