"""Map a feed merchant string to a category from the known-merchant list.

A merchant matches a list name when it starts with that name, ignoring case and
extra spaces, and the name ends at a word boundary: the next character is not a
letter. So "SYSCO PHILA 8827", "US FOODS2201" and "HOME DEPOT #4102" match, but
"SYSCOMM NETWORKS" does not. A miss means the row goes to review, which is the
safe direction. When names overlap, the longest one wins.

The list is our own config, so a malformed list is a setup bug and raises at
load time rather than quietly categorizing against half a list.
"""

import csv
from dataclasses import dataclass
from typing import Iterable, Optional


class CatalogError(ValueError):
    """The merchant list itself is malformed."""


@dataclass(frozen=True)
class Match:
    name: str
    category: str


def normalize(text: str) -> str:
    return " ".join(text.upper().split())


class MerchantCatalog:
    def __init__(self, entries: Iterable[tuple[str, str]]):
        """entries: (merchant name, category) pairs, e.g. dict.items()."""
        self._entries: dict[str, Match] = {}
        for name, category in entries:
            key, category = normalize(name), category.strip()
            if not key or not category:
                raise CatalogError(f"empty merchant or category: {name!r} -> {category!r}")
            existing = self._entries.get(key)
            if existing and existing.category != category:
                raise CatalogError(
                    f"{key!r} is listed as both {existing.category!r} and {category!r}"
                )
            self._entries[key] = Match(name=key, category=category)
        # Longest first, so "HOME DEPOT" would beat a shorter "HOME" entry.
        self._by_length = sorted(self._entries.values(), key=lambda m: -len(m.name))

    @classmethod
    def from_csv(cls, path) -> "MerchantCatalog":
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or {"merchant", "category"} - set(reader.fieldnames):
                raise CatalogError(f"{path}: needs 'merchant' and 'category' columns")
            return cls([(row["merchant"] or "", row["category"] or "") for row in reader])

    def __len__(self) -> int:
        return len(self._entries)

    def match(self, merchant: str) -> Optional[Match]:
        text = normalize(merchant)
        for entry in self._by_length:
            if text.startswith(entry.name):
                rest = text[len(entry.name):]
                if not rest or not rest[0].isalpha():
                    return entry
        return None
