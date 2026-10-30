# Map card decks and the resizable sidebar (2026-10-30)

## Card decks

The decks are visual grouping only. No state, transition or evidence record is merged, changed or hidden from the inspector. The grouping lives in `frontend/src/lib/decks.ts`, and `FlowMap.tsx` uses it to choose what to draw.

- **What is grouped.** Observed states that share a route and a main heading form one deck: the same page or form seen with different field values, messages or validation. Field-fill counts in the summary are ignored for grouping. A different heading (another page, a dialog, a confirmation screen) is a separate deck, so distinct pages and dialogs stay identifiable. Decks with one state are drawn as ordinary nodes.
- **What a collapsed deck shows.** It is drawn as stacked cards with:
  - the heading, route and representative thumbnail (the earliest state);
  - **N observed states**;
  - **N tests recorded** (executed test cases on that form);
  - finding badges by verification status (confirmed, unverified, inconclusive, not reproduced);
  - an **active** marker;
  - how many moves stay inside the deck.
- **Transitions.** A move from or to a collapsed deck is drawn to the deck, with its label, step and selection unchanged. Moves inside a collapsed deck are counted on it instead of drawn. Expanding the deck shows every state and transition again.
- **Automatic grouping.** Multi-state decks start collapsed unless they hold active work. Active work means a run is running and the deck contains the latest recorded state, the target of the latest move, or a state named by a claimed task. Active decks are never collapsed automatically.
- **Manual choices win.** Clicking a deck (or its **Expand** button) expands it. **Collapse N states of this page** on its first state collapses it. **Expand all** / **Collapse all** in the map toolbar apply to every multi-state deck, and the toolbar shows how many are collapsed. Manual choices are kept across live refreshes until another run is opened.
- **Motion.** Nodes glide to their new positions (320 ms), and a collapsing deck fades in, only while a deck opens or closes, never while dragging. Both are off under `prefers-reduced-motion`.
- **Selection.** Selecting a state inside a collapsed deck, for example from Activity, highlights the deck. Expanding it shows the state.

## Resizable sidebar

- A vertical divider sits between the map and the right sidebar (`role="separator"`, with `aria-valuenow`, `aria-valuemin` and `aria-valuemax`).
- **Pointer:** drag it.
- **Keyboard:** focus it, then use Left and Right (Shift for 64 px steps), Home or End for the limits, and Enter (or double-click) to reset.
- **Limits:** 320 px minimum and 760 px maximum. The map always keeps at least 420 px, and the width is re-clamped when the window shrinks.
- **Saved width:** stored in `localStorage` (`flowlens.sidebarWidth`).
- **Narrow screens:** below the `lg` breakpoint the sidebar stacks under the map at full width, and the divider is hidden.

## Checks

`scripts/ui_check_decks.py docs/map-decks [UI_URL API_URL]`: 24/24 on saved run `run_d50048493cc5`. It covers:

- automatic collapse, deck counts and test badges, and unique headings;
- expand, collapse, Expand all and Collapse all;
- every transition drawn when expanded, and evidence opening from an expanded deck;
- records unchanged through the API;
- reduced motion;
- dragging and keyboard resizing, limits, the saved preference and reset;
- 390 px and 1024 px layouts.

Active-work and live-refresh behaviour were checked with an **intercepted fixture**: the same saved record, served as `running`. It is not a live run.

The earlier suites (`ui_check.py` 29/29, `ui_check_review.py` 22/22, `ui_check_queue.py` 14/14, `ui_check_workspace.py` 32/32, `ui_check_report.py` 31/31) still pass. The two that check individual state nodes now click **Expand all** first. The `ui_check_*` scripts read `FLOWLENS_UI` and `FLOWLENS_API` to target another port.

Screenshots: `decks-collapsed.png`, `deck-expanded.png`, `sidebar-resized.png`.
