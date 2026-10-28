"""Evidence files under artifacts/runs/<run_id>/, each registered with a hash."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from flowlens.models.contracts import Evidence
from flowlens.storage.db import Store

_SECRET_PATTERNS = [re.compile(r"sk-or-[A-Za-z0-9_\-]{10,}"), re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{10,}")]


def redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


class EvidenceStore:
    def __init__(self, root: Path, store: Store, run_id: str):
        self.root = root
        self.store = store
        self.run_id = run_id
        self.run_dir = root / "runs" / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def _register(self, kind: str, rel: Path, data: bytes, media_type: str) -> Evidence:
        abs_path = self.root / rel
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(data)
        ev = Evidence(
            run_id=self.run_id,
            kind=kind,  # type: ignore[arg-type]
            path=rel.as_posix(),
            sha256=hashlib.sha256(data).hexdigest(),
            media_type=media_type,
        )
        self.store.put(ev)
        return ev

    def save_screenshot(self, step: int, png: bytes, label: str) -> Evidence:
        rel = Path("runs", self.run_id, "screenshots", f"{step:03d}-{label}.png")
        return self._register("screenshot", rel, png, "image/png")

    def save_json(self, kind: str, name: str, payload: Any) -> Evidence:
        text = redact(json.dumps(payload, indent=2, default=str))
        rel = Path("runs", self.run_id, kind, f"{name}.json")
        return self._register(kind, rel, text.encode("utf-8"), "application/json")
