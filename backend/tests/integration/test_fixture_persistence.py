import httpx

from conftest import FixtureServer


def test_draft_survives_fixture_restart(tmp_path):
    data = tmp_path / "drafts.json"
    s1 = FixtureServer(data).start()
    r = httpx.post(s1.url + "/drafts", data={"title": "T1", "caption": "C1"}, follow_redirects=False)
    assert r.status_code == 303
    location = r.headers["location"].split("?")[0]
    s1.stop()

    s2 = FixtureServer(data).start()
    page = httpx.get(s2.url + location).text
    assert 'value="T1"' in page and ">C1</textarea>" in page
    httpx.post(s2.url + "/__fixture/reset")
    assert "No drafts yet." in httpx.get(s2.url + "/").text
    s2.stop()


def test_reset_not_reachable_by_get(fixture_server):
    assert httpx.get(fixture_server.url + "/__fixture/reset").status_code == 405


def _schedule(url, title, when, ws=None):
    cookies = {"cs_ws": ws} if ws else None
    return httpx.post(url + "/schedule", data={"post_title": title, "publish_date": when},
                      cookies=cookies, follow_redirects=False)


def test_modes_differ_only_on_past_dates(fixture_server, corrected_server):
    # Studio clock is fixed at 2026-06-15 by default.
    assert _schedule(fixture_server.url, "Past", "2026-06-01").status_code == 303  # broken accepts
    r = _schedule(corrected_server.url, "Past", "2026-06-01")
    assert r.status_code == 422 and 'role="alert"' in r.text and "cannot be in the past" in r.text
    for srv in (fixture_server, corrected_server):
        assert _schedule(srv.url, "Future", "2026-07-01").status_code == 303
        assert _schedule(srv.url, "Today", "2026-06-15").status_code == 303
        assert _schedule(srv.url, "", "2026-07-01").status_code == 422
        assert _schedule(srv.url, "Bad", "not-a-date").status_code == 422
    # The pages themselves do not reveal the mode.
    assert httpx.get(fixture_server.url + "/schedule/new").text == httpx.get(corrected_server.url + "/schedule/new").text


def test_workspaces_isolate_records(fixture_server):
    ws = httpx.post(fixture_server.url + "/__fixture/workspaces").json()["workspace"]
    assert _schedule(fixture_server.url, "Only in ws", "2026-07-01", ws).status_code == 303
    assert "Only in ws" in httpx.get(fixture_server.url + "/", cookies={"cs_ws": ws}).text
    assert "Only in ws" not in httpx.get(fixture_server.url + "/").text
    assert httpx.get(fixture_server.url + "/__fixture/workspaces").status_code == 405


def test_legacy_flat_draft_file_is_default_workspace(tmp_path):
    import json
    data = tmp_path / "legacy.json"
    data.write_text(json.dumps({"abc12345": {"id": "abc12345", "title": "Old", "caption": "c",
                                             "created_at": "x", "updated_at": "x"}}))
    s = FixtureServer(data).start()
    assert "Old" in httpx.get(s.url + "/").text and 'value="Old"' in httpx.get(s.url + "/drafts/abc12345").text
    s.stop()
