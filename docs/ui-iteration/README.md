# UI iteration record (2026-10-29)

All screenshots render the saved real run `run_e957eab8645e` (live Chromium + `google/gemini-3-flash-preview`) through the real backend. `after-new-run-finished.png` and `after-run-in-progress.png` show `run_e957eab8645e`'s successor `run_87cd1eda95c3`, which was created through the new launcher dialog. It was a live run: 6 calls, 4,564 tokens, reported US$0.0046.

## Before

`before-1440x900-*.png`, `before-1280x720-*.png`: checkpoint 1 UI.

- The launcher form permanently took a third of the screen.
- States were placed in a hand-written zig-zag, and edge labels overlapped one another.
- The evidence drawer was a list of raw key/value rows and JSON dumps.
- There was no activity view, no keyboard navigation, and no clear split between browser time and model latency.

## Design iteration: map layout (the one recorded change)

| Version | Screenshot | Observation |
|---|---|---|
| 1. Dagre, single left-to-right row | `iter1-1440x900-transition.png`, `iter1-1280x720-map.png` | A linear 5-state run is about 6× wider than tall. Fit-to-view shrank it to roughly 35% zoom, so node labels and edge labels were unreadable at both sizes. The 5-node minimap was an empty white block, and at 1280 px the legend overlapped the thumbnail toggle. |
| 2. Dagre ranks wrapped into rows | `iter2-1440x900-transition.png`, `iter2-1280x720-map.png` | Labels are readable at about 70% zoom. Bezier curves on the wrap-around edges hooked outside the node sides, and nodes dimmed to 45% had poor text contrast. |
| 3. Orthogonal back-edges | `iter3-*.png` | Edges that wrap or go backwards are routed as smooth-step lines through the gap between rows. Dimmed nodes are at 60% opacity, and the minimap only appears for 8 or more states. |

**Rationale.** Dagre still decides rank order, so branches and back-edges keep their structure. The ranks are then wrapped into rows, and the column count is the one that gives the largest fit-to-view zoom for the panel's measured size. This adapts to 1440×900, 1280×720 and stacked narrow layouts without a fixed column count.

**Trade-off.** A wrapped row reads like lines of text, so the left-to-right reading order breaks at each row end. The orthogonal wrap edge makes that break explicit. Graphs with many branches per rank have not been tested against real data yet, because only linear runs exist.

**Later fixes from the browser checks:**
- Selected edges were drawn over their own labels because of a z-index boost, which made the label look faded.
- Edge-label and activity-item accessible names did not contain their visible text (found by axe).
- 11 px metadata on the active run card had 4.31:1 contrast (found by axe).

## After

- `after-1440x900-transition-details.png`, `after-1440x900-activity.png`, `after-1440x900-findings.png`: the main 1440×900 workspace.
- `after-1280x720.png`, `after-1024x768.png`, `after-390x844.png`: smaller viewports.
- `after-screenshot-dialog.png`, `after-launcher-validation.png`: dialogs.
- `after-missing-screenshots.png`, `after-long-content.png`, `after-backend-unreachable.png`: edge and error states, simulated by intercepting requests in the browser check. The backend was not modified.
