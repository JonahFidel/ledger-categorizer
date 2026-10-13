# Ledger categorizer (EXP-412, story 1)

## How to run

Python 3.11+, standard library only.

```sh
python3 categorize.py transactions.csv
```

This writes two files to the current directory: `ledger_lines.csv` (the spec's columns) and `review_notes.csv` (one row per reason a line was flagged, with the feed line number). Use `-o` and `--notes` to choose other paths. The merchant list and operator settings live in `config/`. The command exits 0 whenever a ledger is written; bad rows are flagged, not fatal. It only fails, with a clear message, if the feed or a config file can't be read.

Tests: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest`

`tests/fixtures/expected_full.csv` holds all 56 expected lines. I checked it against a separate ~30-line script that re-derives every line from the spec's wording and shares no code with the project. The two agreed on every row.

## What I found unclear, and would ask before merging

- **"The memo will say PAYMENT or TRANSFER" isn't enough on its own.** Rent's memo is `ACH PAYMENT MAINLINE PROPERTIES`, so a literal reading books $6,500 of rent as a transfer. The code categorizes known merchants *before* it looks for transfers. The landlord is on the merchant list (Rent), so that line never reaches the transfer check. For everything else, a transfer needs the keyword *plus* evidence: either the memo names one of the operator's own accounts, or the other side of the same card payment shows up in the feed. A keyword with no evidence goes to review. Question: where should the operator's own account numbers come from? I read `4421` (card) and `8810` (savings) off this feed into `config/operator.toml`.
- **What "both legs" means when one side is missing.** Every transfer has two sides: money leaves one account and arrives in another. A card payment appears twice in this feed: once leaving the bank account (`+4850.00`) and once arriving on the card (`-4850.00`). Both become Transfer lines. Moves to and from savings appear only once, because the feed covers the card and the bank account but not the savings account, so the savings side never shows up. Those moves get one Transfer line each. Is that the intended reading?
- **The 5-day card-payment match window is my choice.** It's how many days apart the bank side and the card side of one card payment may post: up to 3 business days of ACH lag, which can span a weekend. Both card payments in this sample post on the same day, so the sample doesn't test the window. The tests do.
- **Batches are treated as deltas.** An id keeps the version from its highest batch, and ids that never re-sync keep their only version.
- **I flag more than the spec asks:** bad or ambiguous feed rows (unreadable values are left blank, never guessed), a latest version that still says PENDING, and money moving the wrong way for its category (e.g. money *out* to TOAST PAYOUT). None of these situations occur in the sample data, so they don't change its output.
- **Merchant names must end at a word boundary,** so `SYSCOMM` doesn't count as `SYSCO`. Anything that misses goes to review.

## Where I used AI and where I overrode it

**Tools.** I ran Claude Code (Opus) inside [Firstmate](https://github.com/kunchenguid/firstmate), my agent-supervision setup. Normally Firstmate hands work to separate worker agents. Here I had Claude Code build directly while I reviewed. Each decision and each build phase went onto an interactive [Lavish](https://github.com/kunchenguid/lavish-axi) review page showing real feed rows and the code. I annotated those pages in the browser, and my comments went straight back to Claude Code. From phase 4 on, each phase was its own git branch, merged only after I approved its page. I tried running parallel helper agents for the README and the expected-output file, but Firstmate's guardrails only allow that through its heavier worker process, so I kept it sequential. I used ChatGPT only conversationally, to make sure I understood the assignment. I didn't use it for planning, building, or testing.

**What Claude Code did:** read the spec and feed, spotted the rent trap, proposed options, and wrote the modules and tests. **Where I redirected it:**

- Claude Code offered three ways to detect transfers: merchant list first, an explicit list of transfer phrases, or matching the two sides of a payment. It recommended the first. I chose a combination of the first two, then asked whether failures could always be safe without editing a phrase list for every bank. That question became the evidence rule above.
- Claude Code proposed Ruby. I chose Python because I've been using it in coding interviews lately, so I'm faster at reviewing it.
- Claude Code's plan quietly assumed a 3-day match window. I asked where that came from: it wasn't in the spec. It's now a documented, configurable setting, corrected to 5 days. I also had it renamed from "pairing window" to the more specific `card_payment_match_days`.
- Claude Code's first version stopped the whole run on any malformed row. I rejected that, so now every row still produces a ledger line and anything odd goes to review.
- I kept the merchant list strict, because we maintain it, but had it pinned to the spec table by tests.
- I questioned the 56-line output. Checking it confirmed that batches are deltas.

The full log is in `docs/ai-log.md`.
