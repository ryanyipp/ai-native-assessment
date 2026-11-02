# Checkpoint 1 evidence: live run `run_e957eab8645e`

> **Historical evidence (29 Oct 2026).** Recorded on the code of that day and kept as checkpoint evidence. Current behaviour is described in `docs/architecture.md` and the README.

Provenance: **live** (real Chromium and real `google/gemini-3-flash-preview` calls via OpenRouter), against the synthetic creator-studio fixture. No playback, no mocked model.

- `run-detail.json`: the full API record (run, states, transitions, action results, finding, events, model calls).
- `run-artifacts/`: per-step screenshots, observations and model-call prompt/response JSON (secrets redacted).
- `01-map.png`, `02-state-evidence.png`, `03-transition-evidence.png`: the FlowLens UI rendering this run.

The persistence result (`retained`) is the **explorer's unverified observation**, plus an engine check made in the same browser context. It is not an independently confirmed finding.
