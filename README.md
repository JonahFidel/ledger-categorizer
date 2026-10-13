# Ledger categorizer (EXP-412, story 1)

## How to run

Python 3.11+, standard library only.

```sh
python3 categorize.py transactions.csv
```

This writes `ledger_lines.csv` (the spec's columns) and `review_notes.csv` (one row per reason a line was flagged) to the current directory. Use `-o` and `--notes` to choose other paths. The merchant list and operator settings live in `config/`. The command exits 0 whenever a ledger is written; bad rows are flagged, not fatal. It only fails if the feed or a config file can't be read.

Tests: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest`

## What I found unclear, and would ask before merging

- **"The memo will say PAYMENT or TRANSFER" isn't enough on its own.** Rent's memo is `ACH PAYMENT MAINLINE PROPERTIES`. I check the merchant list first, so rent stays Rent. A transfer then needs the keyword *plus* evidence: either the memo names one of the operator's own accounts, or there's an equal and opposite bank/card leg within 5 days. A keyword with no evidence goes to review. Where should the operator's account numbers really come from? I read `4421` and `8810` off this feed into `config/operator.toml`.
- **"Both legs":** the savings side isn't in the feed, so savings moves have one line. Is that right?
- **The 5-day pairing window is my choice.** ACH lag plus a weekend. Both pairs in this sample post the same day, so the sample doesn't actually test it.
- **Batches are treated as deltas.** An id keeps its highest batch, and ids that never re-sync are kept.
- **Extra review flags beyond the spec:** bad or ambiguous feed rows (blank values, never guessed), a latest version that's still PENDING, and money moving the wrong way for its category (e.g. out to TOAST PAYOUT). None of these fire on this feed.
- **Merchant names must end at a word boundary,** so `SYSCOMM` isn't `SYSCO`. Misses go to review.

## Where I used AI and where I overrode it

I used Claude Code throughout. It read the spec and feed, spotted the rent trap, proposed options, and wrote the modules and tests. I reviewed each phase on a visual board before it merged. Where I redirected it:

- It recommended "merchant list first". I asked whether failures could always be safe, which became the evidence rule above.
- It proposed Ruby; I chose Python.
- Its plan quietly assumed a 3-day pairing window. I asked where that came from: it wasn't in the spec. It's now a documented setting, corrected to 5 days.
- Its first version stopped the whole run on any malformed row. I rejected that, so now every row still produces a ledger line and anything odd goes to review.
- I kept the merchant list strict (we maintain it) but had it pinned to the spec table by tests.
- I questioned the 56-line output; checking it confirmed batches are deltas.

The full log is in `docs/ai-log.md`. `tests/fixtures/expected_full.csv` was cross-checked against an independent script.
