"""Turn deduped feed rows into ledger lines.

Rules, first match wins:
1. Merchant on the known list -> that category. Type from account and sign:
   card + negative = refund, bank + negative = deposit, otherwise purchase.
2. Proven transfer (see transfers.py) -> type transfer, category Transfer.
3. Anything else -> Uncategorized, typed the same way as rule 1.

needs_review is true exactly when there is a reason a human should look:
an unknown merchant, a PAYMENT/TRANSFER with no evidence, a data problem from
the feed, a version that is still pending, or money moving the wrong way for
its category. Every reason is kept so the review queue can show it.
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from ledger.catalog import MerchantCatalog
from ledger.feed import Transaction
from ledger.transfers import TransferRules, find_transfers

UNCATEGORIZED = "Uncategorized"
TRANSFER = "Transfer"
INCOME_CATEGORIES = {"Card sales", "Delivery sales"}  # money should only come in


@dataclass(frozen=True)
class LedgerLine:
    transaction_id: str
    date: Optional[date]
    type: str  # purchase | refund | deposit | transfer
    category: str
    amount: Optional[Decimal]
    reasons: tuple = ()  # why it needs review; empty means it doesn't
    line: int = 0  # source line in the feed
    rule: str = ""  # which rule decided it, for the review board and debugging

    @property
    def needs_review(self) -> bool:
        return bool(self.reasons)


def classify(
    rows: Iterable[Transaction], catalog: MerchantCatalog, rules: TransferRules
) -> list[LedgerLine]:
    rows = list(rows)
    matches = [catalog.match(t.merchant) for t in rows]  # by position: ids may be blank
    clean_unmatched = [t for t, m in zip(rows, matches) if not m and not t.issues]
    transfers = find_transfers(clean_unmatched, rules)
    return [_line(t, m, transfers.get(t.id), rules) for t, m in zip(rows, matches)]


def _line(txn, match, transfer_evidence, rules) -> LedgerLine:
    reasons = list(txn.issues)

    if _still_pending(txn):
        reasons.append("still pending in the latest sync; amount may change when it posts")

    if match:
        category, rule = match.category, f"known merchant {match.name}"
        type_ = _type_by_sign(txn)
        reasons += _direction_problems(txn, category, type_)
    elif transfer_evidence:
        return LedgerLine(
            txn.id, txn.date, "transfer", TRANSFER, txn.amount,
            tuple(reasons), txn.line, f"transfer: {transfer_evidence}",
        )
    else:
        category, type_ = UNCATEGORIZED, _type_by_sign(txn)
        if not txn.issues and rules.has_keyword(txn):
            rule = "says PAYMENT/TRANSFER but no own account named and no matching other leg"
        else:
            rule = "merchant not on the list"
        reasons.append(rule)

    return LedgerLine(txn.id, txn.date, type_, category, txn.amount, tuple(reasons), txn.line, rule)


def _type_by_sign(txn: Transaction) -> str:
    if txn.amount is None or txn.amount >= 0:
        return "purchase"  # spec: "everything else is a purchase"
    if txn.account == "card":
        return "refund"
    return "deposit"  # bank, or an unrecognized account (already flagged by the feed)


def _direction_problems(txn: Transaction, category: str, type_: str) -> list[str]:
    if txn.amount is None:
        return []
    if category in INCOME_CATEGORIES and type_ != "deposit":
        return [f"money going out to a {category} merchant (fee or chargeback?)"]
    if category not in INCOME_CATEGORIES and type_ == "deposit":
        return [f"money coming into the bank from a {category} vendor (refund by ACH?)"]
    return []


def _still_pending(txn: Transaction) -> bool:
    return bool(re.match(r"\s*PENDING\b", txn.memo, re.IGNORECASE))
