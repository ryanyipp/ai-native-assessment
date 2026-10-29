"""Controlled test data for tester and verifier executions.

A fresh browser context does not isolate server records, so every execution
asks the target's harness for a new workspace and sets it as a cookie on the
new context. Agents never see the workspace id or this mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


class SetupError(Exception):
    pass


@dataclass
class TestDataContext:
    __test__ = False

    context_id: str  # label recorded on every record made in this context
    cookies: list[dict]


class WorkspaceProvider:
    def __init__(self, endpoint_path: str, cookie_name: str):
        self.endpoint_path = endpoint_path
        self.cookie_name = cookie_name

    def provision(self, origin: str, label: str) -> TestDataContext:
        if not self.endpoint_path:
            raise SetupError("no test-data workspace provider is configured (FLOWLENS_WORKSPACE_ENDPOINT)")
        try:
            r = httpx.post(origin.rstrip("/") + self.endpoint_path, timeout=10)
            r.raise_for_status()
            body = r.json()
            ws = body["workspace"]
            cookie = body.get("cookie") or self.cookie_name  # the harness may name its own cookie
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise SetupError(f"could not provision a test-data workspace: {type(e).__name__}: {str(e)[:200]}") from e
        host = urlsplit(origin).hostname or "localhost"
        return TestDataContext(
            context_id=f"{label}:{ws}",
            cookies=[{"name": cookie, "value": ws, "domain": host, "path": "/"}],
        )
