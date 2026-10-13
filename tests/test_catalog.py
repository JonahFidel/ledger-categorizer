import pytest

from conftest import ROOT
from ledger.catalog import CatalogError, MerchantCatalog
from ledger.dedupe import latest_versions
from ledger.feed import read_feed

MERCHANTS = ROOT / "config" / "merchants.csv"


@pytest.fixture(scope="module")
def catalog():
    return MerchantCatalog.from_csv(MERCHANTS)


def category(catalog, merchant):
    m = catalog.match(merchant)
    return m.category if m else None


def test_spec_list_loads_all_sixteen_merchants(catalog):
    assert len(catalog) == 16


@pytest.mark.parametrize("merchant,expected", [
    ("SYSCO PHILA 8827", "Food & beverage"),          # store/location junk after the name
    ("HOME DEPOT #4102", "Repairs & maintenance"),
    ("MAINLINE PROPERTIES LLC", "Rent"),
    ("7SHIFTS", "Software"),                           # exact name, starts with a digit
    ("sysco phila", "Food & beverage"),                # case-insensitive
    ("  Home   Depot  #4102 ", "Repairs & maintenance"),  # stray spaces
    ("US FOODS2201", "Food & beverage"),               # digit right after the name
    ("METRO GAS & ELECTRIC", "Utilities"),             # & inside the name
])
def test_known_merchants_match(catalog, merchant, expected):
    assert category(catalog, merchant) == expected


@pytest.mark.parametrize("merchant", [
    "SYSCOMM NETWORKS",          # starts with SYSCO but is a different word
    "GUSTOSO PIZZA",             # starts with GUSTO
    "AMZN MKTP US*2K4X9",
    "THE HOME DEPOT",            # name not at the start
    "TOAST",                     # shorter than the list name TOAST PAYOUT
    "",
])
def test_everything_else_is_no_match(catalog, merchant):
    assert catalog.match(merchant) is None


def test_longest_name_wins_when_names_overlap():
    c = MerchantCatalog([("HOME", "Generic"), ("HOME DEPOT", "Repairs & maintenance")])
    assert c.match("HOME DEPOT #4102").category == "Repairs & maintenance"
    assert c.match("HOME GOODS 12").category == "Generic"


def test_every_feed_merchant_resolves_as_expected(catalog, feed_path):
    merchants = {t.merchant for t in latest_versions(read_feed(feed_path))}
    unmatched = sorted(m for m in merchants if catalog.match(m) is None)
    assert unmatched == [
        "AMZN MKTP US*2K4X9",
        "AMZN MKTP US*7Q1P2",
        "ONLINE PAYMENT TO CARD 4421",   # transfers: handled by the transfer rules, not the list
        "PAYMENT RECEIVED",
        "SHELL OIL 57318",
        "STAPLES 01188",
        "TRANSFER FROM SAVINGS 8810",
        "TRANSFER TO SAVINGS 8810",
    ]


@pytest.mark.parametrize("rows,error", [
    ([("SYSCO", "Food & beverage"), ("sysco", "Utilities")], "listed as both"),
    ([("SYSCO", "")], "empty merchant or category"),
    ([("  ", "Rent")], "empty merchant or category"),
])
def test_malformed_list_is_a_setup_error(rows, error):
    with pytest.raises(CatalogError, match=error):
        MerchantCatalog(rows)


def test_same_name_twice_with_same_category_is_fine():
    assert MerchantCatalog([("SYSCO", "Food & beverage"), ("Sysco", "Food & beverage")])


def test_list_file_needs_both_columns(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("name,category\nSYSCO,Food & beverage\n")
    with pytest.raises(CatalogError, match="columns"):
        MerchantCatalog.from_csv(path)
