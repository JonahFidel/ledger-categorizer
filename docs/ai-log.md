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
- Override: AI's first version stopped the whole run on any malformed row, an unknown account, or two
  conflicting versions of an id in one batch. I rejected that: the command should be as failure-resistant
  as possible, and anything that looks wrong should go to the review queue. Rewritten so that bad values are
  left empty and recorded as issues on the row, conflicting versions keep one line flagged for review, and
  only an unreadable file (missing or missing a column) stops the run.
- AI's code viewer soft-wrapped a long `def` line, which looked like misplaced parentheses. I flagged it;
  AI turned off wrapping on the review board and split two over-long lines in the source.

## Phase 2: merchant catalog
- AI wrote catalog.py + tests. Boundary rule (name must end before a letter, so "SYSCOMM" != "SYSCO")
  came out of my question about what "prefix without a word boundary" meant.
- I agreed a broken merchant list should stop the command (we maintain it), but asked that it be thoroughly
  tested so we know it's good before anything runs: added tests that pin the shipped list to the spec table.
- Phase 1 follow-ups (my calls): unreadable values are left blank; review reasons go to a separate
  review_notes.csv so ledger_lines.csv keeps the spec's exact format; a missing file or column stops with a clear message.
