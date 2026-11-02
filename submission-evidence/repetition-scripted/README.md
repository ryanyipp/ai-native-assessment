# Scripted repetition check

Scripted evidence, not real-model evidence: `scripts/repetition_check.py` on Ticket Desk corrected, 40-call limit. Before is `fe447ec`; after is this commit. Failing live runs stay as recorded: `run_3ded8003b23b`, `run_816054f4e335`, `run_3f84fb9bdc8b`.

| Script | Actions | Explorer actions | Calls | Explore tasks run | Explorer submits (model / setup) | Routes found |
|---|---|---|---|---|---|---|
| Booker, before | 75 | 56 | 32 | 7 | 1 / 3 | 4 |
| Booker, after | 59 | 41 | 28 | 6 | 0 / 3 | 4 |
| Navigator, before | 66 | 47 | 30 | 7 | 0 / 3 | 4 |
| Navigator, after | 59 | 41 | 26 | 6 | 0 / 3 | 4 |

## Coverage tracker

Scripted evidence, Ticket Desk corrected. Coverage (routes, forms, test cases) was unchanged in all three.

| Script | Calls before | Calls after | Actions before | Actions after |
|---|---|---|---|---|
| Booker | 28 | 20 | 59 | 54 |
| Navigator | 26 | 18 | 59 | 54 |
| Looper | 22 | 14 | 49 | 41 |

## Shared exploration memory

Scripted evidence, not real-model evidence: a cooperative script takes whatever the coverage summary offers, on corrected builds, 40-call limit. Before is `e3be56f`. Failing live runs stay as recorded: `run_889273476b47`, `run_d5ebea8378fc`, `run_e77bfee0b249`.

| Site | Calls before | Calls after | Repeated clicks before | After | Routes before / after | Forms before / after | Page structures before / after |
|---|---|---|---|---|---|---|---|
| Leave Desk | 27 | 24 | 8 | 7 | 7 / 7 | 3 / 3 | 9 / 9 |
| Ticket Desk | 20 | 9 | 11 | 1 | 4 / 4 | 2 / 2 | 6 / 5 |

Leave Desk stayed partial in both: one task lay beyond depth 2. Its remaining repeats are mostly Dashboard return trips.
