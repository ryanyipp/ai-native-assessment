# UI iteration 2: browser preview and worker views around the map (2026-10-29)

Goal: make agent activity understandable without inventing any of it. Every image, status and highlight in the new views comes from recorded browser observations, actions and events.

## Before

- `before-no-run.png`: an empty state with a "New run" button.
- `before-launcher.png`: settings in a modal dialog; the target was never shown before starting.
- `before-run-map.png`, `before-run-activity.png`: map plus inspector. To see what a worker was doing, you had to read the Activity list or click edges one by one. There was no per-worker view.

## After

| View | Screenshots | What it shows |
|---|---|---|
| Pre-run | `after-setup-idle.png`, `after-setup-preview.png`, `after-setup-preview-error.png` | A persistent settings panel (URL, goal, workflow including the single-agent baseline, model, limits, key status). The main area holds a **real** server-side screenshot from `POST /api/preview`, labelled "Static screenshot · not interactive" and captured once with its time. It is an image, not an iframe. Loading and error states are shown. The caption says the preview shows the site's default data while runs use fresh workspaces. |
| Run, map main | `after-live-1..3.png` (live run growing), `after-worker-dock.png` | The map is the main view. A docked **worker view** shows a worker selector with a status dot, its state (working on a task, waiting, revoked, or the run's final status), the last recorded action and the screenshot recorded after it. The caption states it refreshes when the worker records an action and is not live video. Clicking the screenshot opens its evidence. |
| Click highlight | `after-click-highlight.png` | Only when the engine recorded the element's page-coordinate bounds **and** the same browser context recorded a screenshot of the page right before that action. The outline is drawn on that before-screenshot, and the caption says so. Otherwise it explains why there is no highlight (for example, old runs have no bounds). |
| Swapped | `after-swapped.png` | "Swap views" makes the worker view the main view and docks a compact map (no legend or toolbar). |
| Map motion | (live run) | Pages and moves accepted after the map first rendered animate once: the node pops, the edge flashes. Old runs and the first render animate nothing. Motion is disabled under `prefers-reduced-motion`. |
| Viewport | — | The map re-fits as pages are accepted only while "Follow new pages" is on. Panning or zooming turns it off, so the view stays still while you inspect. |
| Errors and old runs | `after-failed-run.png` | Failed and partial runs keep their stop-reason callout. Old single-explorer runs load with a worker view for explorer-a. |
| Sizes | `after-1280x720.png`, `after-1024x768.png`, `after-390x844.png` | The dock is a side column at ≥1280 px and stacks below the map on narrower screens. |

## Design iteration (the one recorded change)

1. **Floating dock over the map (rejected).** The first version placed the worker view as a 340 px overlay in the map's top-right corner, to save space. The old regression suite then failed at 1024×768: the overlay covered transition labels, so they could not be clicked. At 1440 px with the history rail open, it also hid part of the map that fit-to-view had placed there.
2. **Dock as a layout region (kept).** It is a side column at ≥1280 px and stacked below the map on narrower screens. The run-history rail now opens by default only at ≥1600 px, so at 1440 px the map keeps about 660 px of width. Trade-off: on 1280–1600 px screens users must open the rail by hand.

**Later fix:** in the swapped view the docked map spent most of its space on the legend and toolbar. It now uses a compact mode.

## Backend support added (only what the views need)

- `POST /api/preview`: allowed origins only. It opens a fresh headless context, navigates once and returns a PNG with its title, final URL and capture time. Nothing is stored, and no model is called.
- `ActionResult.target_box`: for click and fill, the engine records the element's bounding box in full-page coordinates before acting. Old runs have no bounds.

## Checks

- `scripts/ui_check_workspace.py`: 30/30, on the live run `run_a4f1034bfe0f`.
- Earlier suites still pass:
  - `ui_check.py`: 29/29. Its launcher checks now target the settings panel, and one locator was made unambiguous.
  - `ui_check_review.py`: 22/22.
  - `ui_check_queue.py`: 13/13.
- Frontend build and lint clean. Backend pytest: 64 passed.

## Live runs made for this work

| Run | Purpose | Cost |
|---|---|---|
| `run_a4f1034bfe0f` | Checked run, started from the settings panel | US$0.028, partial at its exploration share |
| `run_a54099283d9d` | Started by mistake: a failed script edit re-ran the original live check | US$0.023 |

Both are kept. The workspace check now starts a live run only with `--live`.
