import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledger.feed import Transaction  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def feed_path():
    return FIXTURES / "transactions.csv"


def txn(**overrides) -> Transaction:
    """A valid card purchase; override only the fields a test cares about."""
    fields = dict(
        id="txn_1",
        sync_batch=1,
        date=date(2026, 8, 3),
        account="card",
        merchant="SYSCO PHILA 8827",
        memo="SYSCO PHILA 8827",
        amount=Decimal("10.00"),
    )
    fields.update(overrides)
    if isinstance(fields["amount"], str):
        fields["amount"] = Decimal(fields["amount"])
    return Transaction(**fields)
