#!/usr/bin/env python3
"""Turn a raw transaction feed into categorized ledger lines.

    python3 categorize.py transactions.csv

writes ledger_lines.csv and review_notes.csv to the current directory.
Lines that need a human are flagged, not fatal: the exit code is 0 whenever a
ledger was written. It is non-zero only when the feed or a config file can't be
used at all.
"""

import argparse
import sys
from pathlib import Path

from ledger.catalog import CatalogError, MerchantCatalog
from ledger.classify import classify
from ledger.dedupe import latest_versions
from ledger.feed import FeedError, read_feed
from ledger.transfers import ConfigError, TransferRules
from ledger.writer import write_ledger, write_review_notes

CONFIG = Path(__file__).resolve().parent / "config"


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("feed", help="the provider's transactions.csv")
    p.add_argument("-o", "--output", default="ledger_lines.csv", help="default: %(default)s")
    p.add_argument("--notes", default="review_notes.csv",
                   help="why each flagged line needs review (default: %(default)s)")
    p.add_argument("--merchants", default=CONFIG / "merchants.csv", help="default: config/merchants.csv")
    p.add_argument("--operator", default=CONFIG / "operator.toml", help="default: config/operator.toml")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        catalog = MerchantCatalog.from_csv(args.merchants)
        rules = TransferRules.from_toml(args.operator)
        rows = latest_versions(read_feed(args.feed))
    except FileNotFoundError as e:
        print(f"error: file not found: {e.filename}", file=sys.stderr)
        return 1
    except (FeedError, CatalogError, ConfigError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    lines = classify(rows, catalog, rules)
    write_ledger(lines, args.output)
    write_review_notes(lines, args.notes)

    flagged = sum(line.needs_review for line in lines)
    print(f"{len(lines)} ledger lines written to {args.output}; "
          f"{flagged} need review (reasons in {args.notes})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
