# Ledger categorizer (EXP-412, story 1)

## How to run

Python 3.11+, standard library only.

```sh
python3 categorize.py transactions.csv
```

This writes `ledger_lines.csv` (the spec's columns) and `review_notes.csv` (why each flagged line needs review). Use `-o` and `--notes` to change those paths, respectively. Bad rows are flagged, not fatal. The command only fails if the feed or a config file (`config/`) can't be read.

Tests: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest`. `tests/fixtures/expected_full.csv` (all 56 lines) matched, row for row, a separate script that shares no code with the project.

## Unclear in the story, and what I'd ask

Detail is in [docs/decisions.md](docs/decisions.md).

- **"The memo will say PAYMENT or TRANSFER" isn't enough.** Rent's memo says `ACH PAYMENT`. Known merchants are categorized before transfer detection runs, so rent stays Rent. Any other row is a transfer only with the keyword plus evidence: the memo names an operator account, or the card payment's other side is in the feed. Otherwise it goes to review. *Where should the operator's account numbers come from?* (I read them off this feed.)
- **"Both legs":** a card payment shows up on both the bank and the card, so it gets two lines. Savings isn't in the feed, so a savings move gets one line. *Is that intended?*
- **The window for matching a card payment's two sides is 5 days (`card_payment_match_days`).** That's my choice, not the spec's. The sample doesn't test it.
- **Batches are treated as deltas**, with the highest batch winning per id.
- **I flag more than the spec asks:** bad feed rows, still-PENDING versions, and money moving the wrong way for its category. None occur in the sample.

## Where I used AI and where I overrode it

Claude Code (inside my [Firstmate](https://github.com/kunchenguid/firstmate) setup) read the spec, spotted the rent trap, proposed options, and wrote the code and tests. I reviewed every decision and phase on [Lavish](https://github.com/kunchenguid/lavish-axi) pages. Before merging, [no-mistakes](https://github.com/kunchenguid/no-mistakes) ran an automated code review, live end-to-end tests, and docs and lint checks (no findings), then opened the PR. I used ChatGPT only to understand the assignment. I dictated some prompts with OpenSuperWhisper (voice-to-text) and typed the rest; it's part of my normal workflow. Where I overrode Claude Code:

- It recommended "merchant list first" for transfers. I combined that with its phrase-list option and asked how failures could always be safe, which produced the evidence rule.
- It proposed Ruby. I chose Python, which I'm fastest reviewing after recent interview practice.
- It silently assumed a 3-day match window. I made it a documented, renamed setting (5 days).
- Its first version stopped the whole run on any bad row. I required every row to produce a line, with anything odd sent to review.
- I kept the merchant list strict, but pinned to the spec table by tests.

Full log: [docs/ai-log.md](docs/ai-log.md).
