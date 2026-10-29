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


class FreshContextProvider:
    """Generic website sessions: a new, empty browser context per execution and nothing else.

    Cookies, local storage and cache start empty in every context, so client-side data is
    separated between workers. Data held by the website's own server is NOT isolated: other
    workers, earlier runs and other people using the site may see or change it.
    """

    isolation = ("fresh browser context per execution (client-side storage only); "
                 "the website's server-side data is shared and not isolated")

    def provision(self, origin: str, label: str) -> TestDataContext:
        return TestDataContext(context_id=f"{label}:fresh-context", cookies=[])


WorkspaceProvider.isolation = "fresh browser context and a newly provisioned fixture workspace per execution"


def session_provider(run, settings) -> WorkspaceProvider | FreshContextProvider:
    """Fixture targets get harness workspaces; approved public websites get plain fresh contexts."""
    if getattr(run, "target_profile", "fixture") == "website":
        return FreshContextProvider()
    return WorkspaceProvider(settings.flowlens_workspace_endpoint, settings.flowlens_workspace_cookie)
