"""The committed demo bundle loads into an empty database, labelled as recorded results."""

from flowlens import demo
from flowlens.config import get_settings
from flowlens.services.report import build_report, to_markdown
from flowlens.storage.db import Store


def test_demo_bundle_loads_labelled_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "a"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'demo.db').as_posix()}")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    get_settings.cache_clear()
    try:
        loaded = demo.load(demo.DEFAULT_BUNDLE)
        assert len(loaded) == 7
        assert demo.load(demo.DEFAULT_BUNDLE) == []  # second load skips existing runs
        s = get_settings()
        store = Store(s.database_path)
        statuses = {r.status.value for r in store.list_runs()}
        assert {"completed", "partial", "failed"} <= statuses
        for rid in loaded:
            d = store.detail(rid)
            assert d.run.imported_from.startswith("FlowLens demo bundle")
            assert d.events and all((s.artifacts_path / e.path).is_file() for e in d.evidence)
        md = to_markdown(build_report(store.detail("run_a572a9bf88c5"), s.artifacts_path, "http://localhost:8000"))
        assert "**Recorded result.**" in md and "Confirmed" in md
    finally:
        get_settings.cache_clear()
