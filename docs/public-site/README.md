# Public website support: TodoMVC (2026-10-30)

Target: `https://demo.playwright.dev/todomvc/`, a public demo app that keeps its todos in the browser's `localStorage`.

## What changed

| Area | Behaviour |
|---|---|
| Approval | Typing an origin that is neither configured nor approved shows an approval step in the launcher. It explains three things: only this origin may load, links and redirects elsewhere are blocked, and the site's server data is not isolated. Approving requires ticking an authorisation acknowledgement. Approvals are stored in SQLite (`approved_origins`); `.env` is never edited. A "Revoke approval" link removes one. |
| Scope enforcement | When a run is created it records `target_profile` and `scope_origins`. For an approved website the scope is that one origin. The engine refuses out-of-scope main-frame requests before they are sent. It also catches redirect hops, which Playwright does not route, using request events and a check of the final URL. Nothing from an out-of-scope page is observed or screenshotted: the engine goes back, or to `about:blank`. Previews apply the same scope and return no image if the page left it. The backend enforces all of this whatever the UI does. |
| Sessions | Fixture origins (configured in `.env`) keep their harness workspaces. Approved websites use `FreshContextProvider`: a new browser context per execution, with no cookies or workspace. The run header shows "Public website", and Diagnostics states that the site's server data is shared, not isolated. `provenance.synthetic_fixture` is false for these runs. |
| Actions | `press` (Enter only) and `check` (tick or untick). Checkbox state is observed. Controls inside a list item record the item's text. Where several controls share a role and name (one "Toggle Todo" per row), recorded steps include that row text. A row that is not on screen fails to resolve rather than being guessed. Hash fragments (`#/active`) are kept in recorded paths. After click, press and check, the engine waits two animation frames so single-page-app re-renders show up in the next observation. |
| Preview | Changing the target's origin clears the old screenshot and says so. Changing the URL within the same origin keeps the image but greys it out, with an "Out of date" banner and a "Capture the current target" button. A capture that finishes after the target changed is dropped. |

## Live run `run_15f19bf8bb46`

Single explorer, started from the launcher. Limits: 20 steps, 22 calls, US$0.10. **Result: completed, 10 model calls, US$0.006852 reported.**

The explorer was asked to add "FlowLens milk" and "FlowLens dog", complete milk, view Active, Completed and All, then reload.

| Step | Action | Recorded outcome |
|---|---|---|
| 0 | navigate `/todomvc/` | landed on `/todomvc/#/` |
| 1–4 | fill + **press Enter**, twice | both todos added |
| 5 | **check** "Toggle Todo" in "FlowLens milk" | milk checked, dog unchecked |
| 6 | click "Active" | `#/active`: only dog shown |
| 7 | click "Completed" | `#/completed`: only milk shown (checked) |
| 8 | click "All" | `#/`: both shown |
| 9 | reload | both still shown; milk checked, dog unchecked |

The checkbox states come from the recorded observation artifacts for each step. `run-record.json` holds the run, its actions and its findings. Every recorded page stayed on `https://demo.playwright.dev`.

### What this run does not show

- **The explorer's claim is unverified, and the code check of it failed.** The explorer reported `retained`. Its `checked_values` were row states (`"FlowLens milk": "completed"`). The existing same-context check compares text and field values only; it cannot read checkbox state. It recorded `passed: false`, and its one "match" was a coincidental substring hit on the word "completed". I did not change the check after seeing this result. The actual retention is visible in the step 9 observation, but no component has verified it.
- **This is not data isolation.** TodoMVC stores data in `localStorage`, so a fresh context starts empty. A site that stores data on its server would share that data between workers, runs and other users.
- Only the explorer ran. There was no tester or verifier, and no repetitions.

## Unsupported actions on TodoMVC

- **Editing a todo**: it needs a double-click, which is not an action.
- **Deleting a todo**: the "Delete" button appears only on hover, so it is never in the observation.
- **Keys other than Enter** (Escape to cancel an edit, Tab), drag-and-drop, file upload and native `<select>` choices are not supported.
- **Links to other origins** (todomvc.com, GitHub) are blocked by design.

## Checks

- `scripts/ui_check_public_site.py docs/public-site run_15f19bf8bb46`: 26/26.
  - Approval flow and stored approval.
  - Preview cleared when the origin changes, marked out of date otherwise.
  - Backend refusals for an unapproved preview and run.
  - A same-origin 301 redirect is followed.
  - The run's recorded actions.
  - The header and Diagnostics labels.
  - axe.
- `backend/tests/integration/test_website_targets.py`, against local test servers:
  - Redirects out of scope (one and two hops, via a link, by direct navigation): blocked, with nothing captured.
  - Enter, the checkbox action, filters and reload.
  - Resolving a row's checkbox by its text.
  - Origin normalisation.
  - Approval API and website session profile.
- Backend pytest: 69 passed.
- Fixture workflows unchanged: earlier browser suites 29/29, 22/22, 14/14, 32/32. `ui_check.py` now expects the approval step for an unapproved origin instead of the old ".env" error.

Live spend for this work: US$0.006852 (one run).
