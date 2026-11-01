# Scripted repetition check

Scripted evidence, not real-model evidence: `scripts/repetition_check.py` on Ticket Desk corrected, 40-call limit. Before is `fe447ec`; after is this commit. Failing live runs stay as recorded: `run_3ded8003b23b`, `run_816054f4e335`, `run_3f84fb9bdc8b`.

| Script | Actions | Explorer actions | Calls | Explore tasks run | Explorer submits (model / setup) | Routes found |
|---|---|---|---|---|---|---|
| Booker, before | 75 | 56 | 32 | 7 | 1 / 3 | 4 |
| Booker, after | 59 | 41 | 28 | 6 | 0 / 3 | 4 |
| Navigator, before | 66 | 47 | 30 | 7 | 0 / 3 | 4 |
| Navigator, after | 59 | 41 | 26 | 6 | 0 / 3 | 4 |
