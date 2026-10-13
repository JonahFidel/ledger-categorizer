# AI usage log

Running notes for the README's "where I used AI and where I overrode it" section.
Tool: Claude Code (Opus), driven from a planning conversation plus Lavish review boards per phase.

## Planning
- AI read the spec and feed and flagged the rent trap: txn_1022's memo is "ACH PAYMENT MAINLINE PROPERTIES",
  so a literal "memo says PAYMENT -> transfer" rule books $6,500 of rent as a transfer.
- AI proposed three transfer-detection options and recommended "merchant list first".
  I picked a hybrid instead and asked whether failures could always be safe without editing a phrase list per bank.
  That produced the evidence model: a row skips review only with positive evidence
  (known merchant, memo names one of the operator's own accounts, or a matching opposite leg).
- AI proposed Ruby (their stack); I switched to Python because I'm more fluent in it right now.
- AI's plan said legs pair within "<= 3 days". I asked where that came from: it wasn't in the spec.
  It is now a documented, configurable assumption, and AI corrected it to 5 calendar days
  (1-3 business days of ACH lag can span a weekend).
- I questioned whether 56 output lines was right. Verified: batches are deltas (44 + 4 re-synced + 8 new).

## Phase 1: feed + dedupe
- AI wrote feed.py, dedupe.py and their tests; I reviewed on the phase board.
