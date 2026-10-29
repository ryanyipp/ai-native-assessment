# Review reports and the persistence-check fix (2026-10-30)

## Persistence check: "not evaluated" instead of incidental text matches

Before this change, the explorer's same-session check could count text that happened to be on the page as a match. In the TodoMVC run `run_15f19bf8bb46`, the claim "FlowLens milk: completed" matched only because the page has a "Completed" filter link.

The check now lives in `backend/src/flowlens/verification/persistence.py`, and each claimed value gets one of three statuses:

| Status | When |
|---|---|
| matched / mismatch | Compared against a field's value, or, for entered text with no field left on the page, against the visible text. |
| not evaluated | The claim is about a checkbox or another on/off state ("completed", "active", "checked" …), or names a checkbox's row. This check does not compare such states, so page text can never count as success. |

- The overall outcome is `passed`, `failed` or `not_evaluated`, and `passed` is true only for `passed`.
- **Stored evidence is unchanged.** Records written before this fix are read by the same rules in the report and in the app's Findings panel, so `run_15f19bf8bb46` now shows *Not evaluated* for both of its claims without its stored record being edited.
- The explorer finding's generic stored title ("Saved draft content …") is replaced in the report by a plain question that states the explorer's claim.

## Report

The report is built only from saved run records; nothing calls a model or the target website. It is available in two forms:

- **HTML view:** `GET /api/runs/{id}/report`, opened by **Report** in the run header. It has print styling: the toolbar is hidden, and folded sections say they must be opened to print.
- **Markdown download:** `GET /api/runs/{id}/report.md`, via **Markdown** in the header or the report's own toolbar.

### Order of sections

Written for a team lead:

1. **Header:** goal, website, date, how it was reviewed, and status in plain words, plus an "Incomplete review" banner when the run did not finish.
2. **Summary:** confirmed problems, items needing a decision, and items that did not reproduce; self-checks are counted separately.
3. **Problems to fix (confirmed)**, then **Needs a decision or a further check**, then **Re-checked and not reproduced**. Each finding has:
   - a plain title, its status and what that status means;
   - the requirement, and expected versus observed behaviour;
   - numbered reproduction steps in words;
   - screenshot links labelled by the step they follow;
   - a folded **Technical details** section with ids, stored reasons, re-check attempts and raw records.
4. **What was not checked:**
   - why the run stopped, in plain words (the raw reason is in Diagnostics);
   - forms found but not tested, and test cases that could not run;
   - unfinished, skipped and deferred tasks;
   - requirements not checked;
   - for public websites, the note that server data was not isolated.
5. **Requirements**, with their coverage.
6. **How findings were checked:**
   - *Independent:* a separate verifier replayed the steps in fresh sessions, and code decided the result.
   - *Self-check:* the single-agent baseline checked its own finding.
   - *Unverified / explorer claim:* only the agent that reported it saw it.
7. **About evidence links:** the links work while the FlowLens server that ran the review is running and its artifacts folder is kept. That folder is not version-controlled, and missing files are marked.
8. **Diagnostics** (folded): run id, the goal as stored, internal workflow and status, raw stop reason, model, calls, tokens, cost, limits, target profile, allowed origins, provenance and record counts.

Ids and raw records appear only inside the folded sections. Re-check runs store ids in their goal and finding titles; the main report replaces these with "an earlier finding" or "an earlier review".

## Checks

- `scripts/ui_check_report.py docs/report`: 31/31, on saved runs. No model calls.
  - completed: `run_a572a9bf88c5`, with an independently confirmed finding
  - partial: `run_a54099283d9d`
  - failed: `run_53d7009ff711`
  - single-agent self-check: `run_fc9eba62a54c`
  - TodoMVC: `run_15f19bf8bb46`
  - re-check: `run_40e786578fef`
- What those checks cover:
  - section order;
  - no ids or JSON outside the folded sections;
  - the folded sections open;
  - plain incomplete-run reasons;
  - expected versus observed, steps and status on findings;
  - an evidence link returning the PNG;
  - the self-check label;
  - "Not evaluated" in both the report and the Findings panel;
  - the print media hiding the toolbar;
  - no horizontal overflow at 390 px;
  - the header buttons opening the HTML report and downloading the Markdown file.
- `backend/tests/unit/test_persistence_and_report.py`:
  - checkbox claims are not evaluated even when the word is on the page;
  - text and field values still evaluate;
  - the old record is reinterpreted without being changed;
  - report ordering, labels and missing files;
  - plain reasons for partial runs.

Screenshots: `report-<status>-<run>.png`, `report-print-media.png`, `findings-not-evaluated.png`. Example download: `flowlens-report-run_a572a9bf88c5.md`.
