"""Recorded demo runs: export selected saved runs to a tracked bundle, and load them elsewhere.

Loading needs no API key and makes no model or website calls: it copies saved records and
the evidence files they reference into the configured database and artifacts folder. Every
loaded run is labelled `imported_from`, so the UI and reports show it as a recorded result,
not a run made on this machine.

  python -m flowlens.demo load   [--bundle DIR]              # into DATABASE_URL / ARTIFACTS_DIR
  python -m flowlens.demo export RUN_ID ... [--bundle DIR]   # maintainers only
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path

from flowlens.config import REPO_ROOT, get_settings
from flowlens.models.contracts import Event
from flowlens.storage.db import _TABLES, Store

DEFAULT_BUNDLE = REPO_ROOT / "demo"


def export(run_ids: list[str], bundle: Path, notes: dict[str, str] | None = None) -> None:
    s = get_settings()
    db, root = s.database_path, s.artifacts_path
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {"runs": []}
    conn = sqlite3.connect(db)
    for rid in run_ids:
        records: dict[str, list] = {}
        for table in _TABLES:
            rows = conn.execute(f"SELECT data FROM {table} WHERE run_id=? ORDER BY pk", (rid,)).fetchall()
            records[table] = [json.loads(r[0]) for r in rows]
        if not records["runs"]:
            raise SystemExit(f"{rid}: not in {db}")
        records["events"] = [json.loads(r[0]) for r in
                             conn.execute("SELECT data FROM events WHERE run_id=? ORDER BY seq", (rid,)).fetchall()]
        out = bundle / "runs" / rid
        if out.exists():
            shutil.rmtree(out)
        missing = 0
        for ev in records["evidence"]:
            src = root / ev["path"]
            if src.is_file():
                dst = out / "files" / ev["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            else:
                missing += 1
        out.mkdir(parents=True, exist_ok=True)
        (out / "records.json").write_text(json.dumps(records, ensure_ascii=False, indent=1), "utf-8")
        run = records["runs"][0]
        entry = {"run_id": rid, "status": run["status"], "mode": run["mode"], "target_url": run["target_url"],
                 "recorded_at": run["created_at"], "reported_cost_usd": run["usage"]["reported_cost_usd"],
                 "note": (notes or {}).get(rid, ""), "missing_files": missing}
        manifest["runs"] = [e for e in manifest["runs"] if e["run_id"] != rid] + [entry]
        print(f"exported {rid}: {sum(len(v) for v in records.values())} records, "
              f"{len(records['evidence']) - missing} files, {missing} missing")
    conn.close()
    bundle.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), "utf-8")


def load(bundle: Path, replace: bool = False) -> list[str]:
    s = get_settings()
    root = s.artifacts_path
    root.mkdir(parents=True, exist_ok=True)
    store = Store(s.database_path)
    manifest = json.loads((bundle / "manifest.json").read_text("utf-8"))
    loaded = []
    for entry in manifest["runs"]:
        rid = entry["run_id"]
        src = bundle / "runs" / rid
        records = json.loads((src / "records.json").read_text("utf-8"))
        exists = any(r.id == rid for r in store.list_runs())
        if exists and not replace:
            print(f"skip {rid}: already in {s.database_path}")
            continue
        if exists:
            with sqlite3.connect(s.database_path) as c:
                for table in [*_TABLES, "events"]:
                    c.execute(f"DELETE FROM {table} WHERE run_id=?", (rid,))
        label = f"FlowLens demo bundle (recorded {entry['recorded_at'][:10]})"
        for table, cls in _TABLES.items():
            for raw in records.get(table, []):
                rec = cls.model_validate(raw)
                if table == "runs":
                    rec.imported_from = label
                store.put(rec)
        for raw in records.get("events", []):
            raw = {**raw, "seq": None}
            store.append_event(Event.model_validate(raw))
        files = src / "files"
        if files.is_dir():
            for f in files.rglob("*"):
                if f.is_file():
                    dst = root / f.relative_to(files)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)
        loaded.append(rid)
        print(f"loaded {rid} ({entry['status']}, {entry['mode']}): {entry['note']}")
    return loaded


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m flowlens.demo")
    sub = p.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("load", help="load recorded demo runs (no API key, no model calls)")
    lp.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    lp.add_argument("--replace", action="store_true", help="re-import runs that already exist")
    ep = sub.add_parser("export", help="export saved runs into the bundle (maintainers)")
    ep.add_argument("run_ids", nargs="+")
    ep.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    ep.add_argument("--note", action="append", default=[], metavar="RUN_ID=TEXT")
    a = p.parse_args()
    if a.cmd == "load":
        load(a.bundle, a.replace)
    else:
        export(a.run_ids, a.bundle, dict(n.split("=", 1) for n in a.note))


if __name__ == "__main__":
    main()
