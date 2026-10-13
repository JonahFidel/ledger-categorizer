from datetime import date, timedelta

import pytest

from conftest import ROOT, txn
from ledger.catalog import MerchantCatalog
from ledger.dedupe import latest_versions
from ledger.feed import read_feed
from ledger.transfers import TransferRules, find_transfers

RULES = TransferRules.from_toml(ROOT / "config" / "operator.toml")
D = date(2026, 8, 8)


def bank_payment(id="b", amount="500.00", days=0, memo="ONLINE PAYMENT TO CARD"):
    return txn(id=id, account="bank", merchant=memo, memo=memo, amount=amount,
               date=D + timedelta(days=days))


def card_payment(id="c", amount="-500.00", days=0, memo="ONLINE PAYMENT - THANK YOU"):
    return txn(id=id, account="card", merchant="PAYMENT RECEIVED", memo=memo, amount=amount,
               date=D + timedelta(days=days))


def test_settings_load():
    assert RULES.own_accounts == {"4421": "card", "8810": "savings"}
    assert RULES.keywords == ("PAYMENT", "TRANSFER")
    assert RULES.card_payment_match_days == 5


@pytest.mark.parametrize("memo,expected", [
    ("ONLINE PAYMENT TO CARD 4421", True),
    ("online transfer to savings", True),       # any case
    ("DOORDASH INC PAYOUT", False),              # PAYOUT is not PAYMENT
    ("PAYMENTS PROCESSED", False),               # whole words only
    ("AUTOPAY METRO GAS", False),
])
def test_keyword_is_a_whole_word(memo, expected):
    assert RULES.has_keyword(txn(merchant="X", memo=memo)) is expected


@pytest.mark.parametrize("memo,expected", [
    ("ONLINE PAYMENT TO CARD 4421", "card"),
    ("XFER TO SAV 8810", "savings"),
    ("STORE 44210", None),                       # longer number that contains 4421
    ("REF 14421", None),
    ("NO ACCOUNT HERE", None),
])
def test_own_account_number_must_stand_alone(memo, expected):
    assert RULES.own_account_named(txn(merchant="X", memo=memo)) == expected


def test_real_feed_transfers_and_their_evidence(feed_path):
    catalog = MerchantCatalog.from_csv(ROOT / "config" / "merchants.csv")
    rows = [t for t in latest_versions(read_feed(feed_path)) if not catalog.match(t.merchant)]
    assert find_transfers(rows, RULES) == {
        "txn_1016": "memo names the operator's own card account",
        "txn_1017": "pairs with bank payment txn_1016",
        "txn_1027": "memo names the operator's own savings account",
        "txn_1040": "memo names the operator's own savings account",
        "txn_1051": "memo names the operator's own card account",
        "txn_1052": "pairs with bank payment txn_1051",
    }


def test_keyword_alone_is_not_evidence():
    assert find_transfers([txn(merchant="ACH PAYMENT JOES PLUMBING", memo="ACH PAYMENT JOES PLUMBING",
                               account="bank")], RULES) == {}


def test_own_account_number_without_keyword_is_not_evidence():
    # e.g. a vendor whose store number happens to be 4421
    assert find_transfers([txn(merchant="CORNER STORE 4421", memo="CORNER STORE 4421")], RULES) == {}


def test_legs_pair_without_any_account_number():
    found = find_transfers([bank_payment(), card_payment()], RULES)
    assert found == {"b": "pairs with card payment c", "c": "pairs with bank payment b"}


@pytest.mark.parametrize("gap,pairs", [(0, True), (4, True), (5, True), (6, False)])
def test_card_payment_match_window_is_five_days(gap, pairs):
    found = find_transfers([bank_payment(), card_payment(days=gap)], RULES)
    assert bool(found) is pairs


def test_card_leg_may_post_before_the_bank_leg():
    assert find_transfers([bank_payment(days=2), card_payment()], RULES)


@pytest.mark.parametrize("card", [
    card_payment(amount="-499.99"),                  # amounts differ by a cent
    card_payment(amount="500.00"),                   # card charge, not a card payment
])
def test_pairs_need_equal_and_opposite_amounts(card):
    assert find_transfers([bank_payment(), card], RULES) == {}


def test_coincidental_refund_is_not_paired():
    refund = txn(id="r", account="card", merchant="AMZN MKTP", memo="AMAZON REFUND", amount="-500.00", date=D)
    assert find_transfers([bank_payment(), refund], RULES) == {}


def test_pairing_is_one_to_one_closest_date_first():
    bank = bank_payment(days=3)
    near, far = card_payment(id="near", days=2), card_payment(id="far", days=0)
    found = find_transfers([bank, far, near], RULES)
    assert found == {"b": "pairs with card payment near", "near": "pairs with bank payment b"}
