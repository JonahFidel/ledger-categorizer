"""Write ledger lines to the spec's CSV, plus a side file explaining each review flag.

ledger_lines.csv keeps the spec's exact columns. The reason a line needs review
has no column there, so it goes to review_notes.csv: one row per reason.
"""

import csv
from decimal import Decimal
from typing import Iterable, Optional

from ledger.classify import LedgerLine

LEDGER_COLUMNS = ("transaction_id", "date", "type", "category", "amount", "needs_review")
NOTES_COLUMNS = ("transaction_id", "source_line", "reason")


def format_amount(amount: Optional[Decimal]) -> str:
    if amount is None:
        return ""  # unreadable in the feed; the reason is in review_notes.csv
    if amount.as_tuple().exponent < -2:
        return str(amount)  # never round money silently; the line is already flagged
    return f"{amount:.2f}"


def ledger_row(line: LedgerLine) -> list[str]:
    return [
        line.transaction_id,
        line.date.isoformat() if line.date else "",
        line.type,
        line.category,
        format_amount(line.amount),
        "true" if line.needs_review else "false",
    ]


def write_ledger(lines: Iterable[LedgerLine], path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        out = csv.writer(f)
        out.writerow(LEDGER_COLUMNS)
        out.writerows(ledger_row(line) for line in lines)


def write_review_notes(lines: Iterable[LedgerLine], path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        out = csv.writer(f)
        out.writerow(NOTES_COLUMNS)
        for line in lines:
            for reason in line.reasons:
                out.writerow([line.transaction_id, line.line, reason])
