# Decisions and open questions (detail)

The README has the short version. This file has the reasoning.

## Transfers: keyword plus evidence

The spec says a transfer's memo "will say PAYMENT or TRANSFER". That's necessary but not sufficient: rent's memo is `ACH PAYMENT MAINLINE PROPERTIES`, so a literal reading books $6,500 of rent as a transfer.

Known merchants are categorized *before* transfer detection runs. The landlord is on the merchant list (Rent), so that line never reaches the transfer check. Any other row is a transfer only if it has the keyword plus evidence:

- the memo names one of the operator's own accounts (`4421` card, `8810` savings, in `config/operator.toml`), or
- the other side of the same card payment is in the feed: an equal and opposite bank/card amount within `card_payment_match_days`.

A keyword with no evidence goes to review. The point is that a miss lands in the review queue instead of silently hiding an expense as a transfer.

An own-account number only counts alongside the keyword. Otherwise a vendor whose store number happens to be 4421 would become a silent transfer.

## "Both legs"

Every transfer has two sides: money leaves one account and arrives in another. A card payment appears twice in this feed: leaving the bank account (`+4850.00`) and arriving on the card (`-4850.00`). Both become Transfer lines.

Moves to and from savings appear once, because the feed covers the card and the bank account but not savings. Each gets one Transfer line.

## `card_payment_match_days` = 5

This is how many days apart the bank side and the card side of one card payment may post. ACH usually lands in 1-3 business days, and 3 business days can span a weekend (Thursday to Tuesday). The value isn't in the spec. Both card payments in the sample post on the same day, so only the tests exercise it, at 4 days (match) and 6 days (no match).

## Extra review flags beyond the spec

- Bad or ambiguous feed rows: unreadable values are left blank, never guessed. The same id appearing twice in one batch with different contents is flagged, and so is an unreadable batch number.
- A latest version whose memo still says PENDING, because the amount may change.
- Money moving the wrong way for its category, e.g. money out to TOAST PAYOUT (a fee or chargeback?) or money into the bank from SYSCO (a refund by ACH?).
- An amount with more than 2 decimal places. It is kept exactly as sent, never rounded.

None of these situations occur in the sample data, so they don't change its output. The reasons go to `review_notes.csv`, because the spec's output has no reason column.

## Other choices

- Batches are deltas. An id keeps the version from its highest batch, and ids that never re-sync keep their only version.
- A merchant name must end at a word boundary, so `SYSCOMM` doesn't count as `SYSCO`. Overlapping names resolve to the longest match.
- The command only fails when the feed is missing or lacks a column, or when a config file is broken. Config is ours, so it is strict and pinned by tests.

## Tools

I ran Claude Code (Opus) inside [Firstmate](https://github.com/kunchenguid/firstmate), my agent-supervision setup. Firstmate normally hands work to separate worker agents. Here I had Claude Code build directly while I reviewed.

Each decision and each build phase went onto an interactive [Lavish](https://github.com/kunchenguid/lavish-axi) review page with real feed rows and the code. I annotated those pages in the browser, and my comments went straight back to Claude Code.

From phase 4 on, each phase was its own git branch, merged only after I approved its page. Parallel helper agents were blocked by Firstmate's guardrails, so the phases ran one after another.

I used ChatGPT only conversationally, to understand the assignment, never for planning, building or testing.

I dictated some of my prompts with OpenSuperWhisper, a voice-to-text tool, and typed many others. It's part of my normal workflow, not something used for every prompt.

Before phases 2-6 merged, I ran them through [no-mistakes](https://github.com/kunchenguid/no-mistakes): an automated code review, an agent driving the real command end to end against both expected files, and docs and lint checks. It found nothing to fix, then pushed the branch and opened PR #1, which I merged.
