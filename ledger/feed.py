"""Read the provider's raw transaction feed into typed rows.

Bad data never stops the run: a value that can't be parsed is left empty and
the problem is recorded on the row, so the row still becomes a ledger line and
lands in the review queue. Only a file that can't be read at all (missing, or
missing a required column) raises.
"""

import csv
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

REQUIRED_COLUMNS = ("id", "sync_batch", "date", "account", "merchant", "memo", "amount")
ACCOUNTS = ("card", "bank")


class FeedError(ValueError):
    """The feed file as a whole can't be read."""


@dataclass(frozen=True)
class Transaction:
    id: str
    sync_batch: Optional[int]
    date: Optional[date]
    account: str  # "card" or "bank" when valid; the raw value otherwise (with an issue)
    merchant: str
    memo: str
    amount: Optional[Decimal]  # positive = money leaving the operator
    line: int = field(default=0, compare=False)  # source line, for review notes
    issues: tuple = field(default=(), compare=False)  # why this row needs a human


def read_feed(path) -> list[Transaction]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise FeedError(f"{path}: missing column(s): {', '.join(missing)}")
        return parse_rows(reader)


def parse_rows(rows: Iterable[dict], first_line: int = 2) -> list[Transaction]:
    return [_parse_row(row, line) for line, row in enumerate(rows, start=first_line)]


def _parse_row(row: dict, line: int) -> Transaction:
    issues = []

    def text(col):
        return (row.get(col) or "").strip()

    def bad(col, why):
        issues.append(f"{col} {why}: {text(col)!r}")
        return None

    txn_id = text("id")
    if not txn_id:
        bad("id", "is empty")

    try:
        sync_batch = int(text("sync_batch"))
    except ValueError:
        sync_batch = bad("sync_batch", "is not an integer")

    try:
        txn_date = date.fromisoformat(text("date"))
    except ValueError:
        txn_date = bad("date", "is not YYYY-MM-DD")

    account = text("account").lower()
    if account not in ACCOUNTS:
        bad("account", f"is not one of {', '.join(ACCOUNTS)}")

    try:
        amount = Decimal(text("amount"))
        if not amount.is_finite():
            amount = bad("amount", "is not a finite number")
        elif amount.as_tuple().exponent < -2:
            issues.append(f"amount has more than 2 decimal places: {text('amount')!r}")
    except InvalidOperation:
        amount = bad("amount", "is not a number")

    return Transaction(
        id=txn_id,
        sync_batch=sync_batch,
        date=txn_date,
        account=account,
        merchant=text("merchant"),
        memo=text("memo"),
        amount=amount,
        line=line,
        issues=tuple(issues),
    )
