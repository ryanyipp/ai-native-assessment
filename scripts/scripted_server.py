r"""The real FlowLens API with a scripted model, for demonstrations that must not spend credit.

Only the model is replaced: the API, coordinator, queue, Chromium and fixture are the real ones. Runs are
labelled mocked_model. The model URL points at a dead address and the key is a placeholder, so no paid call
can succeed. Data goes to its own folder, not the main database. Needs dev dependencies (the test script).

Usage (repo root): backend\.venv\Scripts\python scripts\scripted_server.py [--port 8010] [--delay 0]
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "backend" / "tests"), str(REPO / "backend" / "tests" / "integration")]

p = argparse.ArgumentParser()
p.add_argument("--port", type=int, default=8010)
p.add_argument("--delay", type=float, default=0.0, help="seconds each scripted model call takes")
p.add_argument("--data", default=str(REPO / "artifacts" / "scripted-demo"))
p.add_argument("--origin", default="http://localhost:5174")
a = p.parse_args()
os.environ.update(OPENROUTER_API_KEY="scripted-placeholder-not-a-key", OPENROUTER_BASE_URL="http://127.0.0.1:9/api/v1",
                  ARTIFACTS_DIR=a.data, DATABASE_URL=f"sqlite:///{(Path(a.data) / 'flowlens.db').as_posix()}",
                  FLOWLENS_ALLOWED_ORIGINS=a.origin)

import uvicorn  # noqa: E402

import flowlens.api.runs as api  # noqa: E402
from flowlens.main import app  # noqa: E402
from flowlens.services.llm import ScriptedClient  # noqa: E402
from test_queue import queue_script  # noqa: E402


class DelayedScript(ScriptedClient):
    async def complete(self, messages, max_tokens, reasoning_tokens=None):
        await asyncio.sleep(a.delay)
        return await super().complete(messages, max_tokens, reasoning_tokens)


api.OpenRouterClient = lambda settings, model=None: DelayedScript(queue_script()[0])
uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
