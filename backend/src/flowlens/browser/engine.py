"""Playwright execution of validated, bounded browser commands.

The model never touches Playwright directly. It sees an Observation whose
interactive elements carry short ids (e1, e2 ...) and proposes one action that
references them. The engine validates the action, checks origins, executes it,
and returns an ActionResult plus a fresh Observation.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright.async_api import Error as PlaywrightError

from flowlens.models.contracts import (
    CheckAction,
    ClickAction,
    ControlRef,
    FillAction,
    InspectAction,
    NavigateAction,
    Observation,
    ObservedElement,
    PressAction,
    ReloadAction,
)

MAX_ELEMENTS = 60
MAX_TEXT = 1500
ACTION_TIMEOUT_MS = 5000
NAV_TIMEOUT_MS = 15000

# Collects visible interactive elements and tags each with data-flowlens-id.
_INSPECT_JS = r"""
(maxElements) => {
  document.querySelectorAll('[data-flowlens-id]').forEach(e => e.removeAttribute('data-flowlens-id'));
  const visible = el => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const clean = t => (t || '').replace(/\s+/g, ' ').trim().slice(0, 120);
  const nameOf = el => {
    if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'));
    const lb = el.getAttribute('aria-labelledby');
    if (lb) return clean(lb.split(' ').map(id => document.getElementById(id)?.innerText || '').join(' '));
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return clean(l.innerText); }
    const wrap = el.closest('label'); if (wrap) return clean(wrap.innerText);
    if (el.tagName === 'INPUT' && ['submit','button'].includes(el.type)) return clean(el.value);
    return clean(el.innerText || el.getAttribute('placeholder') || el.getAttribute('title') || '');
  };
  const roleOf = el => {
    if (el.getAttribute('role')) return el.getAttribute('role');
    const t = el.tagName.toLowerCase();
    if (t === 'a') return 'link';
    if (t === 'button') return 'button';
    if (t === 'textarea') return 'textbox';
    if (t === 'select') return 'combobox';
    if (t === 'input') {
      const ty = (el.type || 'text').toLowerCase();
      if (['submit','button','reset'].includes(ty)) return 'button';
      if (ty === 'checkbox') return 'checkbox';
      if (ty === 'radio') return 'radio';
      return 'textbox';
    }
    return t;
  };
  const sel = 'a[href], button, input:not([type=hidden]), textarea, select, [role=button], [role=link], [contenteditable=true]';
  const forms = [...document.forms];
  const userInvalid = el => { try { return el.matches(':user-invalid'); } catch (e) { return false; } };
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    if (out.length >= maxElements) break;
    if (!visible(el)) continue;
    const id = 'e' + (out.length + 1);
    el.setAttribute('data-flowlens-id', id);
    const tag = el.tagName.toLowerCase();
    const isField = ['input','textarea','select'].includes(tag);
    out.push({
      id, tag, role: roleOf(el), name: nameOf(el),
      input_type: tag === 'input' ? (el.type || 'text') : null,
      value: isField ? String(el.value ?? '').slice(0, 300) : null,
      href: tag === 'a' ? el.getAttribute('href') : null,
      disabled: !!el.disabled,
      required: !!el.required,
      form_index: el.form ? forms.indexOf(el.form) : null,
      validation_message: (isField && (userInvalid(el) || el.getAttribute('aria-invalid') === 'true'))
        ? (clean(el.validationMessage) || 'invalid') : null,
      checked: (tag === 'input' && ['checkbox','radio'].includes(el.type)) ? !!el.checked
        : (['checkbox','switch','radio'].includes(el.getAttribute('role') || '') ? el.getAttribute('aria-checked') === 'true' : null),
      _el: el,
    });
  }
  // Controls inside a list item or row carry its text; name_shared marks a role+name seen more than once
  // (one "Toggle Todo" per row), so those controls are recorded with their row.
  const count = {};
  for (const o of out) { const k = o.role + '|' + o.name; count[k] = (count[k] || 0) + 1; }
  for (const o of out) {
    const item = o._el.closest('li, tr, [role=row], [role=listitem], [role=option]');
    o.context = item ? (clean(item.innerText) || null) : null;
    o.name_shared = count[o.role + '|' + o.name] > 1;
    delete o._el;
  }
  const headings = [...document.querySelectorAll('h1,h2,h3')].filter(visible).map(h => clean(h.innerText)).slice(0, 12);
  const status = [...document.querySelectorAll('[role=status],[role=alert],[aria-live]')]
    .filter(visible).map(s => clean(s.innerText)).filter(Boolean).slice(0, 6);
  const alerts = [...document.querySelectorAll('[role=alert]')]
    .filter(visible).map(s => clean(s.innerText)).filter(Boolean).slice(0, 6);
  return { title: document.title, headings, elements: out, status, alerts, text: (document.body?.innerText || '').replace(/\s+/g, ' ').trim() };
}
"""


class ActionRejected(Exception):
    """The command failed validation before touching the browser."""


class ControlResolutionError(Exception):
    """A semantic control matched zero or several elements in a fresh observation."""


def _norm(t: str) -> str:
    return " ".join((t or "").split()).casefold()


def resolve_control(obs: Observation, control: ControlRef) -> ObservedElement:
    """Find the one element matching role + accessible name (+ input type) in this observation."""
    matches = [
        e for e in obs.elements
        if _norm(e.role) == _norm(control.role) and _norm(e.name) == _norm(control.name)
        and (control.input_type is None or (e.input_type or None) == control.input_type)
        and (control.context is None or _norm(e.context or "") == _norm(control.context))
    ]
    if not matches:
        raise ControlResolutionError(f"no {control.describe()} in the current page ({obs.url})")
    if len(matches) > 1:
        ids = ", ".join(m.id for m in matches)
        raise ControlResolutionError(f"{control.describe()} is ambiguous: {len(matches)} matches ({ids})")
    return matches[0]


def control_of(el: ObservedElement) -> ControlRef:
    return ControlRef(role=el.role, name=el.name, input_type=el.input_type,
                      context=el.context if el.name_shared else None)


@dataclass
class Execution:
    ok: bool
    error: str | None
    target_description: str | None
    url_before: str
    url_after: str
    started_at: datetime
    duration_ms: int
    observation: Observation
    screenshot_png: bytes
    target_element: ObservedElement | None = None  # resolved element, from the pre-action observation
    # Page-coordinate bounds of the target element just before the action (for click highlights).
    target_box: dict | None = None


def normalise_route(url: str) -> str:
    """Path with id-like segments replaced, query/fragment dropped."""
    path = urlsplit(url).path or "/"
    parts = []
    for seg in path.split("/"):
        if re.fullmatch(r"\d+|[0-9a-f]{6,}|[0-9a-f-]{20,}", seg, re.I):
            parts.append(":id")
        else:
            parts.append(seg)
    return "/".join(parts) or "/"


def state_signature(obs: Observation) -> tuple[str, str]:
    """(signature, route). Policy v1: route + control roles/names + headings + field filled flags.

    Field values are excluded (so a reload with retained values maps to the same
    state) but empty/filled is kept, which distinguishes a blank form from a
    filled one. Status messages are included so a "saved" banner is a state.
    """
    route = normalise_route(obs.url)
    controls = sorted(
        f"{e.role}:{e.name}"
        + (f":{'checked' if e.checked else 'unchecked'}" if e.checked is not None
           else f":{'filled' if e.value else 'empty'}" if e.value is not None else "")
        for e in obs.elements
    )
    raw = "|".join([route, ";".join(obs.headings), ";".join(controls), ";".join(sorted(obs.status_messages))])
    return hashlib.sha256(raw.encode()).hexdigest()[:16], route


def page_structure(obs: Observation) -> tuple[str, str]:
    """(structure, layout) used to decide which new states deserve exploration.

    structure: route + headings + control roles/names + status and alert messages,
    WITHOUT field filled/empty flags. Two states that differ only in which fields are
    filled share a structure. Dialogs, errors and saved/persistence banners change
    headings, controls or messages, so they keep distinct structures.
    layout: the same without messages, so an error outcome of a form shares the form's layout.
    """
    route = normalise_route(obs.url)
    controls = ";".join(sorted(f"{e.role}:{e.name}" for e in obs.elements))
    layout = "|".join([route, ";".join(obs.headings), controls])
    msgs = ";".join(sorted(set(obs.status_messages) | set(obs.alert_messages)))
    return (hashlib.sha256(f"{layout}|{msgs}".encode()).hexdigest()[:16],
            hashlib.sha256(layout.encode()).hexdigest()[:16])


def origin_of(url: str) -> str:
    s = urlsplit(url)
    return f"{s.scheme}://{s.netloc}".lower()


class BrowserEngine:
    def __init__(self, allowed_origins: list[str], headless: bool = True, storage_state: str | None = None,
                 cookies: list[dict] | None = None):
        self.allowed_origins = {o.lower().rstrip("/") for o in allowed_origins}
        self.headless = headless
        self.storage_state = storage_state
        self.cookies = cookies or []  # e.g. a provisioned test-data workspace
        # Called before every action; raising here refuses the action (lease revoked).
        self.before_action = None
        self.closed_by_coordinator = False
        self._pw = None
        self._browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.last_observation: Observation | None = None
        # Main-frame navigations (including each redirect hop) that left the allowed origins.
        self._escapes: list[str] = []

    def in_scope(self, url: str) -> bool:
        return origin_of(url) in self.allowed_origins

    @staticmethod
    def _main_navigation(request) -> bool:
        try:
            return request.is_navigation_request() and request.frame.parent_frame is None
        except PlaywrightError:
            return False

    def _on_request(self, request) -> None:
        if self._main_navigation(request) and request.url.startswith("http") and not self.in_scope(request.url):
            self._escapes.append(request.url)

    async def _guard_route(self, route) -> None:
        """Refuse main-frame document requests to other origins before they are sent."""
        req = route.request
        if self._main_navigation(req) and req.url.startswith("http") and not self.in_scope(req.url):
            self._escapes.append(req.url)
            await route.abort("blockedbyclient")
        else:
            await route.fallback()

    async def __aenter__(self) -> BrowserEngine:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        # A fresh, isolated context per worker.
        self.context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800}, storage_state=self.storage_state or None
        )
        if self.cookies:
            await self.context.add_cookies(self.cookies)
        # Scope is enforced for every main-frame navigation: before it is sent (route), and for
        # redirect hops, which are followed without routing (request events + a final URL check).
        await self.context.route("**/*", self._guard_route)
        self.context.on("request", self._on_request)
        self.page = await self.context.new_page()
        self.page.set_default_timeout(ACTION_TIMEOUT_MS)
        return self

    async def fence(self) -> None:
        """Coordinator-side close of an expired attempt's context; later actions fail."""
        self.closed_by_coordinator = True
        if self.context:
            try:
                await self.context.close()
            except PlaywrightError:
                pass

    async def __aexit__(self, *exc) -> None:
        if self.context and not self.closed_by_coordinator:
            await self.context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    def check_origin(self, url: str) -> None:
        if origin_of(url) not in self.allowed_origins:
            raise ActionRejected(f"origin {origin_of(url)} is not in the allowed target origins")

    @staticmethod
    async def _read(page) -> Observation:
        raw = await page.evaluate(_INSPECT_JS, MAX_ELEMENTS)
        return Observation(
            url=page.url,
            title=raw["title"],
            headings=raw["headings"],
            elements=[ObservedElement(**e) for e in raw["elements"]],
            text_excerpt=raw["text"][:MAX_TEXT],
            status_messages=raw["status"],
            alert_messages=raw["alerts"],
            invalid_fields=[e["name"] for e in raw["elements"] if e.get("validation_message")],
        )

    async def observe(self) -> Observation:
        assert self.page
        obs = await self._read(self.page)
        self.last_observation = obs
        return obs

    async def peek(self, url: str) -> tuple[Observation, bytes]:
        """Open a same-origin page in a second tab of this context (same session and test data),
        observe it and close it. The main page and its element ids are untouched. GET only."""
        if self.before_action is not None:
            self.before_action()
        self.check_origin(url)
        assert self.context
        tab = await self.context.new_page()
        try:
            await tab.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
            if not self.in_scope(tab.url):
                raise ActionRejected(f"check page redirected out of scope to {origin_of(tab.url)}")
            obs = await self._read(tab)
            png = await tab.screenshot(full_page=True)
        finally:
            await tab.close()
        return obs, png

    def _element(self, element_id: str) -> ObservedElement:
        obs = self.last_observation
        el = next((e for e in obs.elements if e.id == element_id), None) if obs else None
        if el is None:
            raise ActionRejected(f"element {element_id} is not in the latest observation")
        if el.disabled:
            raise ActionRejected(f"element {element_id} is disabled")
        return el

    async def execute(self, action) -> Execution:
        """Run one validated action. Failures are returned, not raised, so they are recorded."""
        if self.before_action is not None:
            self.before_action()
        assert self.page
        page = self.page
        started = datetime.now(UTC)
        t0 = time.perf_counter()
        url_before = page.url
        target = None
        target_el = None
        target_box = None
        error = None
        self._escapes.clear()
        try:
            if isinstance(action, InspectAction):
                pass
            elif isinstance(action, NavigateAction):
                url = action.url
                if url.startswith("/") and url_before.startswith("http"):
                    url = origin_of(url_before) + url
                self.check_origin(url)
                target = url
                await page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
            elif isinstance(action, ReloadAction):
                await page.reload(wait_until="load", timeout=NAV_TIMEOUT_MS)
            elif isinstance(action, (ClickAction, FillAction, PressAction, CheckAction)):
                el = self._element(action.element_id)
                target_el = el
                target = f"{el.role} '{el.name}'"
                loc = page.locator(f'[data-flowlens-id="{action.element_id}"]')
                target_box = await self._page_box(loc)
                if isinstance(action, FillAction):
                    if el.role not in ("textbox", "combobox", "searchbox") and el.tag not in ("input", "textarea"):
                        raise ActionRejected(f"element {action.element_id} ({el.role}) is not fillable")
                    if el.checked is not None:
                        raise ActionRejected(f"element {action.element_id} is a checkbox; use check")
                    await loc.fill(action.value)
                elif isinstance(action, CheckAction):
                    if el.checked is None:
                        raise ActionRejected(f"element {action.element_id} ({el.role}) is not a checkbox or switch")
                    if el.context and el.name_shared:
                        target += f" in '{el.context}'"
                    # A click, not set_checked: many apps re-render the row on change, so Playwright's
                    # post-click check of the same element fails. The next observation shows the result.
                    if el.checked != action.checked:
                        await loc.click()
                elif isinstance(action, PressAction):
                    await loc.press(action.key)
                    try:
                        await page.wait_for_load_state("load", timeout=NAV_TIMEOUT_MS)
                    except PlaywrightError:
                        pass
                else:
                    if el.href and not el.href.startswith("#"):
                        self.check_origin(urljoin(url_before, el.href))
                    await loc.click()
                    try:
                        await page.wait_for_load_state("load", timeout=NAV_TIMEOUT_MS)
                    except PlaywrightError:
                        pass
            else:
                raise ActionRejected(f"unsupported action {type(action).__name__}")
        except ActionRejected as e:
            error = f"rejected: {e}"
        except PlaywrightError as e:
            error = f"browser error: {str(e).splitlines()[0][:300]}"
        if isinstance(action, (ClickAction, PressAction, CheckAction)) and error is None:
            await self._settle()
        # Guard against any navigation or redirect that left the approved scope. Nothing from an
        # out-of-scope page is observed or captured: go back, or to a blank page if that fails.
        off_page = not self.in_scope(page.url) and page.url != "about:blank"
        if off_page or self._escapes:
            where = origin_of(self._escapes[0] if self._escapes else page.url)
            error = (f"{error}; " if error else "") + f"rejected: left the approved scope ({where}); blocked"
            if off_page:
                try:
                    await page.go_back(wait_until="load", timeout=NAV_TIMEOUT_MS)
                except PlaywrightError:
                    pass
                if not self.in_scope(page.url):
                    await page.goto("about:blank")
        duration_ms = int((time.perf_counter() - t0) * 1000)
        obs = await self.observe()
        png = await page.screenshot(full_page=True)
        return Execution(
            ok=error is None,
            error=error,
            target_description=target,
            url_before=url_before,
            url_after=page.url,
            started_at=started,
            duration_ms=duration_ms,
            observation=obs,
            screenshot_png=png,
            target_element=target_el,
            target_box=target_box,
        )

    async def _settle(self) -> None:
        """Let single-page apps finish re-rendering (hashchange, state updates) before observing."""
        try:
            await self.page.evaluate(
                "() => new Promise(r => setTimeout(() => requestAnimationFrame(() => requestAnimationFrame(r)), 30))")
        except PlaywrightError:
            pass

    async def _page_box(self, loc) -> dict | None:
        """Bounds in full-page coordinates (viewport box + scroll), or None if not measurable."""
        try:
            box = await loc.bounding_box(timeout=1000)
            sx, sy = await self.page.evaluate("[window.scrollX, window.scrollY]")
        except PlaywrightError:
            return None
        if not box:
            return None
        return {"x": round(box["x"] + sx), "y": round(box["y"] + sy),
                "width": round(box["width"]), "height": round(box["height"])}
