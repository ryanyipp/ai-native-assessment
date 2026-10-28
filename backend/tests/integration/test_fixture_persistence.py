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
