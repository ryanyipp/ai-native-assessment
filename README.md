
# FlowLens

[![CI](https://github.com/ryanyipp/ai-native-assessment/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ryanyipp/ai-native-assessment/actions/workflows/ci.yml)

FlowLens uses four AI workers to explore staging websites, test forms against written requirements, and present findings with replay evidence.

## Watch the demo

A narrated, real-model review of Ticket Desk, showing two seeded defects, their verification replays and the generated report.

https://github.com/user-attachments/assets/72c1741d-8bca-4116-9913-50885a93d59c

## Quick start

Prerequisite: Docker Desktop or Docker Engine with Compose v2.24 or later. The first build downloads about 1–2 GB.

```sh
git clone https://github.com/ryanyipp/ai-native-assessment.git
cd ai-native-assessment
docker compose up --build
```

Open http://localhost:5173. The stack uses host ports 5173 (UI), 8000 (API) and 5174–5179 (three fixture apps, broken and corrected builds).

- **Browse recorded runs (no key, no cost):** choose **Explore recorded demos**. Eight saved runs load at start, including the video's run, and are labelled as recorded results.
- **Live reviews (paid):** copy `.env.example` to `.env`, set `OPENROUTER_API_KEY`, then run `docker compose up --build` again. Choose **Start a review**, pick a target such as `http://localhost:5176/` (Ticket Desk, broken), enter a goal and the requirements, and click **Start live run**. Each run is capped at US$0.50 and 60 model calls by default.

`docker compose down -v` removes the containers and the data volume. Native setup without Docker, configuration and the list of recorded runs are in [docs/setup.md](docs/setup.md).

## How it works

Four model-driven workers share a task queue:

1. **Explore:** Explorer A and B claim different tasks, discover pages and forms, and consult shared exploration memory.
2. **Test:** the input tester proposes form cases against the supplied requirements. Browser code executes them and records evidence.
3. **Verify:** the verifier checks whether a requirement applies and selects an assertion. Code evaluates it in two fresh browser replays.

Python code manages task ownership, retries, budgets and result acceptance. It also builds the flow map records and generates reports from saved evidence.

A confirmed finding reproduced the requirement violation in both replays. Correctness still depends on the model selecting an appropriate requirement and assertion.

![Multi-agent shared queue: Explorer A and B hand forms to the input tester, which hands candidates to the verifier for confirmed, not reproduced or inconclusive outcomes; a Python coordinator manages claims, dependencies, leases, retries, deduplication and budgets](docs/images/flowlens-architecture.png)

[Architecture and handoffs →](docs/architecture.md)

## Validation and CI

GitHub Actions runs offline backend tests and frontend lint, type-checking and build checks. Browser integration tests use local fixtures with mocked models; real-model runs and manual UI checks provide separate evidence. CI does not deploy the application.

[Setup and checks →](docs/setup.md#checks)

## Evaluation

| Six completed models | Shared queue | Single agent |
|---|---|---|
| Supported detections | **18/36** | **13/36** |

Benefits varied by model, and the queue cost more. A supported detection failed its assertion on the broken build and passed on the corrected build. These small experiments used earlier code and development fixtures; incomplete models are excluded.

[Methods, per-model results and records →](docs/model-comparison.md)

## Known limitations

FlowLens reviews a bounded slice of a site: one user role, Chromium, authorised origins and fixed call, cost and time budgets. A finished review does not mean the site passed.

- **Explicit requirements are needed for confirmation.** Applicability and assertion selection remain model judgements.
- **Coverage is bounded.** Repeated navigation and unsampled states can leave gaps.
- **Some controls are unsupported.** Radio buttons and file inputs are not tested.
- **Model output can fail.** Invalid plans may leave forms untested; incomplete cases receive no verdict.
- **Recovery handles worker stalls within a running backend.** Reviews interrupted by a backend restart are not resumed.
- **Browser isolation does not isolate website data.** Only the supplied fixtures provide separate test-data workspaces.

## The demo run

The video shows `run_7bbdcc167bb6`, a shared-queue review with Gemini 3 Flash of Ticket Desk's broken build. The goal was "Test and check the pages and inputs", with four supplied requirements. It confirmed both seeded defects, each in two fresh replays: 7 tickets accepted (T1) and a cancelled booking still listed (T4). It used 13 model calls and cost US$0.017. The run is bundled in `demo/` and opens without an API key.

## Documentation and attribution

- [docs/setup.md](docs/setup.md): native setup, configuration, recorded runs, checks and CI.
- [docs/architecture.md](docs/architecture.md): workers, queue, leases and recovery, assertions, current behaviour.
- [docs/model-comparison.md](docs/model-comparison.md): benchmark method and results.
- [docs/development-log.md](docs/development-log.md): build history and problems found along the way.
- [docs/plan.md](docs/plan.md) and [AGENTS.md](AGENTS.md): the agreed plan and the working rules; AGENTS.md lists what was implemented.
- [docs/attribution.md](docs/attribution.md): libraries and AI assistance. The code was written with Claude, as the commit co-author trailers show; Ryan set the scope, ran and recorded the demos, and reviewed the work.
