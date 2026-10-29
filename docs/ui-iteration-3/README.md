# UI iteration 3: simplified workspace with an agent activity strip (2026-10-29)

**Before:** see `docs/ui-iteration-2/after-*.png`. That layout had a two-line header full of metadata (run id, model, calls, tokens, cost, mode, build label), and a docked worker view with "Swap views" that took a column away from the map.

## After

| Change | Screenshots |
|---|---|
| **Compact header:** goal, target and status, plus a visible injected-fault label. Run id, workflow, provenance, model, usage, cost, build label and the full stop reason move into **Diagnostics**. Failed, partial and interrupted runs keep a one-line stop reason in the header ("Stopped early" or "Stopped on an error"). | `after-run.png`, `after-diagnostics.png`, `after-failed-run.png` |
| **Agent activity strip:** one labelled icon per agent in the run's actual workflow. <br>• Rosters: shared queue = Explorer A, Explorer B, Input tester, Verifier; sequential = Explorer A, Input tester, Verifier; single explorer = Explorer A; single-agent baseline = Single agent; re-check = Verifier. <br>• State per icon (several can be active at once): active = it holds a claimed task, or in sequential modes produced the latest action; waiting; not started; did not run; done. <br>• "N active now" counts claimed tasks; there is no progress percentage. <br>• Animations: active icons bob and pulse gently. When a new `handoff_created` event arrives, "Latest handoff A → B" slides in once and the receiver's icon flashes. Handoffs already recorded when the page opened do not animate. | `after-fixture-active-handoff.png` |
| **Clicking an agent** selects it and opens the **Browser** tab with its latest recorded screenshot. | `after-browser-tab.png`, `after-click-highlight.png` |
| **One right sidebar:** Browser · Evidence · Activity · Findings. A map selection opens Evidence there. The dock and swap are gone, so the map has all the remaining width. | `after-run.png` |
| **Evidence from setup steps:** a worker's latest action may be a setup or replay step with no map transition. Its screenshot now opens the page it was recorded on; if there is none, the button says so. | — |
| **Reduced motion:** every strip and map animation is off. | (checked) |
| **Sizes:** at 1280, 1024 and 390 px the header wraps, and the sidebar tabs drop their icons below 1280 px and scroll if needed. | `after-1280x720.png`, `after-1024x768.png`, `after-390x844.png` |

## Design iteration

1. **First version (rejected):** the draft (`draft-header-diagnostics.png`) kept tab icons at every width. With four sidebar tabs, the tab row overflowed the 400 px sidebar at 1280, 1024 and 390 px. The older regression suites caught it (horizontal-overflow checks).
2. **Fix (kept):** icons are hidden below 1280 px and the tab row scrolls rather than overflows.

**Trade-off:** the worker selector is kept inside the Browser tab as well as the strip, so the sidebar still works on its own on narrow screens where the strip wraps.

## How simultaneous activity was verified

No live run was active while checking. To test the rendering of real event shapes without spending, `scripts/ui_check_workspace.py` serves an **intercepted fixture** built from saved run `run_a4f1034bfe0f`:
- status set to running;
- two of its real explore tasks marked claimed, with `task_claimed` events;
- after 2.5 s, one appended `handoff_created` event.

This is labelled as a fixture in the script and is not presented as a live run. The earlier live run (`run_a4f1034bfe0f`, iteration 2) showed new map records animating live.

## Checks

- `ui_check_workspace.py`: 32/32 (settings and preview, strip, Diagnostics, sidebar, evidence, highlight, fixture activity and handoff, reduced motion, per-workflow rosters on old, sequential, single-agent and failed runs, three sizes, accessibility).
- `ui_check.py` 29/29, `ui_check_review.py` 22/22, `ui_check_queue.py` 14/14. Their header assertions now open Diagnostics.
- Build and lint clean. No backend changes. No live spend.
