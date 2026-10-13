"""Read the provider's raw transaction feed into typed, validated rows.

The feed is trusted for shape, not content: a malformed row stops the run with
its line number rather than being skipped, because a silently dropped
transaction is a wrong ledger.
"""

import csv
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterable

REQUIRED_COLUMNS = ("id", "sync_batch", "date", "account", "merchant", "memo", "amount")
ACCOUNTS = ("card", "bank")


class FeedError(ValueError):
    """The feed can't be turned into a ledger as-is."""


@dataclass(frozen=True)
class Transaction:
    id: str
    sync_batch: int
    date: date
    account: str  # "card" or "bank"
    merchant: str
    memo: str
    amount: Decimal  # positive = money leaving the operator
    line: int = field(default=0, compare=False)  # source line, for error messages only


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
    def text(col):
        return (row.get(col) or "").strip()

    def fail(col, why):
        raise FeedError(f"line {line}: {col} {why}: {row.get(col)!r}")

    txn_id = text("id")
    if not txn_id:
        fail("id", "is empty")

    try:
        sync_batch = int(text("sync_batch"))
    except ValueError:
        fail("sync_batch", "is not an integer")

    try:
        txn_date = date.fromisoformat(text("date"))
    except ValueError:
        fail("date", "is not YYYY-MM-DD")

    account = text("account").lower()
    if account not in ACCOUNTS:
        fail("account", f"is not one of {ACCOUNTS}")

    try:
        amount = Decimal(text("amount"))
    except InvalidOperation:
        fail("amount", "is not a number")
    if not amount.is_finite():
        fail("amount", "is not a finite number")

    return Transaction(
        id=txn_id,
        sync_batch=sync_batch,
        date=txn_date,
        account=account,
        merchant=text("merchant"),
        memo=text("memo"),
        amount=amount,
        line=line,
    )
