"""Decide which rows are money moving between the operator's own accounts.

A row is a transfer only with positive evidence. It must say PAYMENT or
TRANSFER (as a whole word) and also either:
- name one of the operator's own accounts (e.g. "... TO CARD 4421"), or
- have a matching other leg: a bank outflow and a card inflow of the same
  amount within a few days, both carrying the keyword.

A keyword with no evidence is not a transfer; the classifier sends it to
review. Rows that matched a known merchant never get here, which is what keeps
rent ("ACH PAYMENT MAINLINE PROPERTIES") out.
"""

import re
import tomllib
from dataclasses import dataclass
from typing import Iterable

from ledger.feed import Transaction


class ConfigError(ValueError):
    """The operator settings file is malformed."""


@dataclass(frozen=True)
class TransferRules:
    own_accounts: dict[str, str]  # last4 -> account name
    keywords: tuple[str, ...]
    card_payment_match_days: int

    @classmethod
    def from_toml(cls, path) -> "TransferRules":
        try:
            with open(path, "rb") as f:
                cfg = tomllib.load(f)
            return cls(
                own_accounts={str(a["last4"]): a["name"] for a in cfg["own_accounts"]},
                keywords=tuple(k.upper() for k in cfg["transfers"]["keywords"]),
                card_payment_match_days=int(cfg["transfers"]["card_payment_match_days"]),
            )
        except (tomllib.TOMLDecodeError, KeyError, TypeError, ValueError) as e:
            raise ConfigError(f"{path}: invalid operator settings ({e!r})") from e

    def has_keyword(self, txn: Transaction) -> bool:
        text = f"{txn.merchant} {txn.memo}".upper()
        return any(re.search(rf"\b{re.escape(k)}\b", text) for k in self.keywords)

    def own_account_named(self, txn: Transaction) -> str | None:
        text = f"{txn.merchant} {txn.memo}"
        for last4, name in self.own_accounts.items():
            if re.search(rf"(?<!\d){re.escape(last4)}(?!\d)", text):
                return name
        return None


def find_transfers(candidates: Iterable[Transaction], rules: TransferRules) -> dict[str, str]:
    """Return {transaction id: evidence} for every candidate proven to be a transfer.

    Candidates are rows that didn't match a known merchant and have no data
    problems; this function checks the keyword itself.
    """
    keyed = [t for t in candidates if rules.has_keyword(t)]
    evidence: dict[str, str] = {}

    for t in keyed:
        name = rules.own_account_named(t)
        if name:
            evidence[t.id] = f"memo names the operator's own {name} account"

    for bank_leg, card_leg in _pair_legs(keyed, rules.card_payment_match_days):
        evidence.setdefault(bank_leg.id, f"pairs with card payment {card_leg.id}")
        evidence.setdefault(card_leg.id, f"pairs with bank payment {bank_leg.id}")

    return evidence


def _pair_legs(keyed: list[Transaction], window_days: int):
    """Match bank outflows to card inflows of equal amount, one-to-one, closest dates first."""
    bank = [t for t in keyed if t.account == "bank" and t.amount > 0]
    card = [t for t in keyed if t.account == "card" and t.amount < 0]
    options = sorted(
        (
            (b, c)
            for b in bank
            for c in card
            if b.amount == -c.amount and abs((b.date - c.date).days) <= window_days
        ),
        key=lambda pair: (abs((pair[0].date - pair[1].date).days), pair[0].line, pair[1].line),
    )
    used: set[str] = set()
    for b, c in options:
        if b.id not in used and c.id not in used:
            used.update((b.id, c.id))
            yield b, c
