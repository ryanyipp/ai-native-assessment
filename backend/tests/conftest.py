import importlib.util
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

FIXTURE_APP = Path(__file__).resolve().parents[2] / "fixtures" / "creator-studio" / "app.py"


def load_fixture_module():
    spec = importlib.util.spec_from_file_location("creator_studio_app", FIXTURE_APP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FixtureServer:
    def __init__(self, data_path: Path):
        self.mod = load_fixture_module()
        self.mod.DATA_PATH = data_path
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self._server = None
        self._thread = None

    def start(self):
        cfg = uvicorn.Config(self.mod.app, host="127.0.0.1", port=self.port, log_level="warning")
        self._server = uvicorn.Server(cfg)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        for _ in range(100):
            try:
                httpx.get(self.url + "/", timeout=0.5)
                return self
            except httpx.HTTPError:
                time.sleep(0.05)
        raise RuntimeError("fixture did not start")

    def stop(self):
        self._server.should_exit = True
        self._thread.join(timeout=5)


@pytest.fixture
def fixture_server(tmp_path):
    srv = FixtureServer(tmp_path / "drafts.json").start()
    yield srv
    srv.stop()
