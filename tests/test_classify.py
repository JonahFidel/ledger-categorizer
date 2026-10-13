import csv
from decimal import Decimal

import pytest

from conftest import FIXTURES, ROOT, txn
from ledger.catalog import MerchantCatalog
from ledger.classify import classify
from ledger.dedupe import latest_versions
from ledger.feed import read_feed
from ledger.transfers import TransferRules

CATALOG = MerchantCatalog.from_csv(ROOT / "config" / "merchants.csv")
RULES = TransferRules.from_toml(ROOT / "config" / "operator.toml")


def one(**overrides):
    [line] = classify([txn(**overrides)], CATALOG, RULES)
    return line


@pytest.fixture(scope="module")
def feed_lines():
    rows = latest_versions(read_feed(FIXTURES / "transactions.csv"))
    return {line.transaction_id: line for line in classify(rows, CATALOG, RULES)}


def test_matches_the_given_first_fifteen(feed_lines):
    with open(FIXTURES / "expected_first_15.csv", newline="") as f:
        for row in csv.DictReader(f):
            line = feed_lines[row["transaction_id"]]
            assert (str(line.date), line.type, line.category, line.amount,
                    str(line.needs_review).lower()) == (
                row["date"], row["type"], row["category"], Decimal(row["amount"]),
                row["needs_review"]), row["transaction_id"]


def test_only_unknown_merchants_need_review_in_the_real_feed(feed_lines):
    flagged = {i: l.reasons for i, l in feed_lines.items() if l.needs_review}
    assert flagged == {
        "txn_1006": ("merchant not on the list",),   # Amazon
        "txn_1020": ("merchant not on the list",),   # Shell
        "txn_1028": ("merchant not on the list",),   # Staples
        "txn_1037": ("merchant not on the list",),   # Amazon refund
    }


@pytest.mark.parametrize("txn_id,type_,category", [
    ("txn_1022", "purchase", "Rent"),                    # memo says "ACH PAYMENT", still rent
    ("txn_1016", "transfer", "Transfer"),                # bank -> card payment
    ("txn_1017", "transfer", "Transfer"),                # card side of the same payment
    ("txn_1027", "transfer", "Transfer"),                # to savings, one leg
    ("txn_1040", "transfer", "Transfer"),                # from savings, one leg
    ("txn_1018", "refund", "Food & beverage"),           # Sysco credit keeps its category
    ("txn_1024", "refund", "Repairs & maintenance"),
    ("txn_1036", "refund", "Smallwares & supplies"),
    ("txn_1037", "refund", "Uncategorized"),             # refund from an unknown merchant
    ("txn_1004", "deposit", "Card sales"),
    ("txn_1020", "purchase", "Uncategorized"),           # posted Shell charge, not the $1 hold
])
def test_spec_rules_on_the_real_feed(feed_lines, txn_id, type_, category):
    assert (feed_lines[txn_id].type, feed_lines[txn_id].category) == (type_, category)


def test_transfers_are_not_reviewed(feed_lines):
    assert not any(l.needs_review for l in feed_lines.values() if l.type == "transfer")


def test_payment_with_no_evidence_goes_to_review_with_the_reason():
    line = one(account="bank", merchant="ACH PAYMENT JOES PLUMBING", memo="ACH PAYMENT JOES PLUMBING",
               amount="450.00")
    assert (line.type, line.category) == ("purchase", "Uncategorized")
    assert line.reasons == ("says PAYMENT/TRANSFER but no own account named and no matching other leg",)


def test_unknown_bank_inflow_is_an_uncategorized_deposit_for_review():
    line = one(account="bank", merchant="CASH DEPOSIT", memo="BRANCH DEPOSIT", amount="-300.00")
    assert (line.type, line.category, line.needs_review) == ("deposit", "Uncategorized", True)


def test_still_pending_version_is_flagged():
    line = one(memo="PENDING - SYSCO")
    assert line.category == "Food & beverage"
    assert line.reasons == ("still pending in the latest sync; amount may change when it posts",)


@pytest.mark.parametrize("account,merchant,amount,reason", [
    ("bank", "TOAST PAYOUT", "35.00", "money going out to a Card sales merchant (fee or chargeback?)"),
    ("card", "UBER EATS PAYOUT", "-20.00", "money going out to a Delivery sales merchant (fee or chargeback?)"),
    ("bank", "SYSCO 8827", "-90.00", "money coming into the bank from a Food & beverage vendor (refund by ACH?)"),
])
def test_money_moving_the_wrong_way_for_its_category_is_flagged(account, merchant, amount, reason):
    line = one(account=account, merchant=merchant, memo=merchant, amount=amount)
    assert line.reasons == (reason,)


def test_feed_problems_still_produce_a_line_for_review():
    line = one(amount=None, issues=("amount is not a number: '12,00'",))
    assert line.transaction_id == "txn_1"
    assert (line.type, line.category, line.amount) == ("purchase", "Food & beverage", None)
    assert line.reasons == ("amount is not a number: '12,00'",)


def test_rows_with_problems_are_never_treated_as_transfers():
    line = one(account="bank", merchant="TRANSFER TO SAVINGS 8810", memo="TRANSFER TO SAVINGS 8810",
               date=None, issues=("date is not YYYY-MM-DD: 'soon'",))
    assert line.type != "transfer" and line.needs_review
