# Diagnosis of run_156b7b84dc3b (2026-10-30)

| | |
|---|---|
| Run | Shared queue, `https://automationexercise.com/` (approved public website) |
| Status | Partial: "queue drained; tasks {'done': 2, 'blocked': 2, 'failed': 5}" |
| Usage | 12 model calls, US$0.0349, 4 truncated replies |

The diagnosis used Docker's saved records, read through its API. The click timeout was also reproduced with the browser engine alone, with no model calls. The run's records are unchanged.

## 1. Click timeouts (steps 2, 3 and 21): an ad interstitial covered the page

After a click on "Products", the URL became `/#google_vignette`. That is Google's full-page interstitial ad, which held the page in place of the navigation. The next clicks then waited 5 s and failed. The run kept only the first line of the error, `Locator.click: Timeout 5000ms exceeded.`

Reproducing it gave the full call log:

```
- <iframe … id="aswift_3" title="Advertisement" aria-label="Advertisement" src="https://googleads.g.double…></iframe>
  from <ins … data-vignette-loaded="true" class="adsbygoogle adsbygoogle-noablate">…</ins> subtree intercepts pointer events
- retrying click action … (repeated until the 5 s timeout)
```

The ad iframe covered the full 1280×800 viewport. The site's own controls were not slow.

## 2. Five explore tasks failed setup: ads changed the page on every visit

The failed tasks reported "direct path reached a different state" and "recipe reached a different state". Comparing the recorded observation with the replayed one showed the differences were ad content:

- the links "Audit Quality", "Compare Broadband", "Try Cloud Tools", "Test case templates", "Software products" and "here";
- a status message, "Automation skills training".

So a page's fingerprint changed on every fresh visit. One task also failed at "click link 'View Cart'". That link sits in the "Added!" dialog, which opens only after the add-to-cart request returns, and replay looked for it straight away.

## 3. Two form tests blocked: hidden reasoning used the reply budget

All four truncated replies came from input-tester planning calls:

| Call | Output cap | Output tokens | Hidden reasoning |
|---|---|---|---|
| 1 | 1400 | 1385 | 1342 |
| 2 | 2800 | 2785 | 2684 |
| 3 | 1400 | 1385 | 1341 |
| 4 | 2800 | 2785 | 2684 |

These calls asked for a 384-token reasoning budget; the provider ignored it. Doubling the cap, the previous repair, just gave the reasoning more room.

Across all recorded runs:

- **Token budget** (tester calls): 88 of 230 used over 600 reasoning tokens, and 22 were truncated.
- **`effort: "low"`** (explorer calls): median 0 reasoning tokens, and 2 of 877 truncated.

## 4. Report explanation

For partial runs, the report said "stopped at a time, step or budget limit". That was wrong here: the queue drained because its tasks failed or were blocked.

## Fixes (bounded; timeouts not raised, clicks not forced)

| Cause | Fix | Where |
|---|---|---|
| Ad interstitial covers controls | Requests to known ad-network hosts (Google ads, DoubleClick and a short list of others) are refused at the browser-context level. The site's own requests are unaffected. | `engine.AD_HOST_SUFFIXES`, `_guard_route` |
| Any other cover over a control | One bounded recovery: press Escape, let the page settle, retry once with a 2 s timeout. If the cover stays, the action fails as `blocked: <element> covers the element`, and the recovery is recorded. The click is never forced. | `BrowserEngine._pointer` |
| Truncated traces | Failed actions keep the full Playwright call log (up to 4,000 characters) in `ActionResult.error_detail`, and the recovery note in `ActionResult.recovery`. | engine, runner |
| Ad content changing fingerprints | Observation ignores controls and messages inside ad containers. `#google_vignette` is dropped from recorded paths. | `_INSPECT_JS`, `relative_path` |
| A control that appears after a request | Replay re-observes up to 3 times, 500 ms apart, before reporting a missing control. Ambiguity fails at once. | `replay.resolve_with_wait` |
| Reasoning using the reply budget | Tester and verifier calls use `effort: "low"`. If a truncated reply was at least 75% hidden reasoning, the one retry uses `effort: "minimal"` at the same cap. Truncated visible text still gets a doubled cap. Each call records the reasoning setting it sent. | `llm.reasoning_request`, `review.ReviewRun.model` |
| Wrong stop explanation | For a drained queue, the report names the failed and blocked tasks and their recorded causes, and the status line no longer mentions limits. Untested forms with the same heading are listed once. | `report.plain_stop`, `task_problems` |

## Verified without model calls

- **Real site, browser engine only:**
  - `/`, `/product_details/1` and `/view_cart` each gave 1 fingerprint over 3 fresh visits, where the home page alone gave several in the run.
  - "Products" and both "View Product" clicks navigated normally.
  - The replayed "View Cart" dialog link resolved.
  - 8 ad requests were blocked.
- **Regression tests on local pages:** `backend/tests/integration/test_run156_regressions.py` (8 tests).
  - The interceptor is named from the real trace.
  - Ad requests are blocked, ad links are ignored and fingerprints are stable.
  - Escape recovery succeeds.
  - A cover that stays fails within one short retry, with the full trace.
  - Replay waits for a control that appears late.
  - Reasoning settings and the minimal-reasoning retry.
  - The report names the real cause.
- **Updated test:** `test_correctness_pass.py` now expects minimal reasoning for a reasoning-starved truncation and a doubled cap for long visible text.

## Not yet verified

- **The provider's response to `effort: "minimal"`:** it needs a model call.
- **A full live run on the site:** it was not repeated. The next live attempt should confirm both.
- **The Escape recovery on real overlays:** it may not clear every kind. Covers that stay are reported as blocked, not retried further.
