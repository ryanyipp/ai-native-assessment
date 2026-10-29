"""The held-out ticket-desk fixture: builds differ only in the documented rules."""

import importlib.util
from pathlib import Path

import httpx

from conftest import FixtureServer

APP = Path(__file__).resolve().parents[3] / "fixtures" / "ticket-desk" / "app.py"


class TicketDesk(FixtureServer):
    def __init__(self, data_path, mode):
        spec = importlib.util.spec_from_file_location("ticket_desk_app", APP)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.DATA_PATH, self.mod.MODE = data_path, mode
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"


def _book(url, tickets, email="a@b.c", ws=None):
    return httpx.post(url + "/events/1/book", data={"name": "N", "email": email, "tickets": str(tickets)},
                      cookies={"td_ws": ws} if ws else None, follow_redirects=False)


def test_ticket_desk_builds(tmp_path):
    b = TicketDesk(tmp_path / "b.json", "broken").start()
    c = TicketDesk(tmp_path / "c.json", "corrected").start()
    try:
        assert _book(b.url, 7).status_code == 303 and _book(c.url, 7).status_code == 422
        for srv in (b, c):
            assert _book(srv.url, 0).status_code == 422 and _book(srv.url, 3, email="nope").status_code == 422
            ws = httpx.post(srv.url + "/__fixture/workspaces").json()
            assert ws["cookie"] == "td_ws"
            loc = _book(srv.url, 2, ws=ws["workspace"]).headers["location"].split("?")[0]
            httpx.post(srv.url + loc + "/cancel", cookies={"td_ws": ws["workspace"]})
            listing = httpx.get(srv.url + "/", cookies={"td_ws": ws["workspace"]}).text
            assert ("ticket(s)" in listing) == (srv is b)  # broken still lists the cancelled booking
        assert httpx.get(b.url + "/events/1/book").text == httpx.get(c.url + "/events/1/book").text
    finally:
        b.stop()
        c.stop()
