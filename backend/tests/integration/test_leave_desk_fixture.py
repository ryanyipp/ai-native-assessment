"""The held-out leave-desk fixture: builds differ only in the documented rules."""

import importlib.util
import socket
import sys
from pathlib import Path

import httpx

from conftest import FixtureServer

REPO = Path(__file__).resolve().parents[3]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class LeaveDesk(FixtureServer):
    def __init__(self, data_path, mode):
        self.mod = _load("leave_desk_app", REPO / "fixtures" / "leave-desk" / "app.py")
        self.mod.DATA_PATH, self.mod.MODE = data_path, mode
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"


def test_leave_desk_builds(tmp_path):
    b = LeaveDesk(tmp_path / "b.json", "broken").start()
    c = LeaveDesk(tmp_path / "c.json", "corrected").start()
    try:
        check = _load("check_leave_desk", REPO / "scripts" / "check_leave_desk.py")
        assert check.run(b.url, c.url) == []
    finally:
        b.stop()
        c.stop()


def test_workspace_reset_and_isolation(tmp_path):
    srv = LeaveDesk(tmp_path / "w.json", "corrected").start()
    try:
        ws = httpx.post(srv.url + "/__fixture/workspaces").json()
        assert ws["cookie"] == "ld_ws"
        form = {"leave_type": "Annual", "start_date": "2026-08-01", "end_date": "2026-08-02"}
        httpx.post(srv.url + "/requests", data=form, cookies={"ld_ws": ws["workspace"]})
        assert "Remaining balance: 10 days" in httpx.get(srv.url + "/", cookies={"ld_ws": ws["workspace"]}).text
        other = httpx.post(srv.url + "/__fixture/workspaces").json()["workspace"]
        assert "Remaining balance: 12 days" in httpx.get(srv.url + "/", cookies={"ld_ws": other}).text
        httpx.post(srv.url + "/__fixture/reset")
        page = httpx.get(srv.url + "/requests", cookies={"ld_ws": ws["workspace"]}).text
        assert page.count("<li>") == 3
        assert "Remaining balance: 12 days" in httpx.get(srv.url + "/", cookies={"ld_ws": ws["workspace"]}).text
    finally:
        srv.stop()
