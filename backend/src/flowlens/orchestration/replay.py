"""Reaching a recorded state and repeating semantic steps in a fresh browser context.

Element ids are never reused across observations: every click/fill step is
resolved by role + accessible name against the observation the engine just made.
No match or several matches is an explicit failure.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from flowlens.browser.engine import BrowserEngine, ControlResolutionError, Execution, resolve_control, state_signature
from flowlens.models.contracts import (
    CheckAction,
    ClickAction,
    FillAction,
    NavigateAction,
    PressAction,
    ReloadAction,
    SemanticStep,
    SetupRecipe,
)

Recorder = Callable[[dict, Execution, str], Awaitable[None]]


@dataclass
class Reached:
    ok: bool
    strategy: str | None
    error: str | None
    execution: Execution | None


CONTROL_WAIT_TRIES = 3
CONTROL_WAIT_MS = 500


async def resolve_with_wait(eng: BrowserEngine, obs, control):
    """Resolve a control, re-observing a few times if it is not there yet.

    Some controls appear only after a request returns (an "Added!" dialog with "View Cart" after
    add-to-cart; run_156b7b84dc3b). Bounded: at most CONTROL_WAIT_TRIES re-observations,
    CONTROL_WAIT_MS apart. Several matches is ambiguity, not lateness, so it fails at once.
    """
    for attempt in range(CONTROL_WAIT_TRIES + 1):
        try:
            return resolve_control(obs, control)
        except ControlResolutionError as e:
            if "ambiguous" in str(e) or attempt == CONTROL_WAIT_TRIES:
                raise ControlResolutionError(
                    f"{e}" + (f" (after waiting {CONTROL_WAIT_TRIES * CONTROL_WAIT_MS} ms)" if attempt else "")) from e
            await eng.page.wait_for_timeout(CONTROL_WAIT_MS)
            obs = await eng.observe()


async def execute_step(eng: BrowserEngine, origin: str, step: SemanticStep) -> tuple[dict, Execution]:
    """Raises ControlResolutionError if the control cannot be resolved uniquely."""
    if step.type == "navigate":
        action = NavigateAction(url=origin.rstrip("/") + (step.path or "/"))
    elif step.type == "reload":
        action = ReloadAction()
    else:
        assert step.control is not None
        obs = eng.last_observation or await eng.observe()
        el = await resolve_with_wait(eng, obs, step.control)
        if step.type == "fill":
            action = FillAction(element_id=el.id, value=step.value or "")
        elif step.type == "press":
            action = PressAction(element_id=el.id, key=step.key or "Enter")
        elif step.type == "check":
            action = CheckAction(element_id=el.id, checked=step.checked is not False)
        else:
            action = ClickAction(element_id=el.id)
    return action.model_dump(), await eng.execute(action)


async def reach_state(eng: BrowserEngine, origin: str, recipe: SetupRecipe, record: Recorder) -> Reached:
    """Try the direct path, then the full semantic recipe. Success requires the recorded signature."""
    errors = []
    if recipe.direct_path:
        action, ex = await execute_step(eng, origin, SemanticStep(type="navigate", path=recipe.direct_path))
        await record(action, ex, f"setup: open {recipe.direct_path}")
        sig = state_signature(ex.observation)[0]
        if ex.ok and sig == recipe.expected_signature:
            return Reached(True, "direct", None, ex)
        errors.append(f"direct path reached a different state ({sig} != {recipe.expected_signature})"
                      if ex.ok else f"direct path failed: {ex.error}")
    if recipe.steps:
        ex = None
        for i, step in enumerate(recipe.steps, 1):
            try:
                action, ex = await execute_step(eng, origin, step)
            except ControlResolutionError as e:
                errors.append(f"recipe step {i} ({step.describe()}): {e}")
                return Reached(False, "recipe", "; ".join(errors), ex)
            await record(action, ex, f"setup {i}: {step.describe()}")
            if not ex.ok:
                errors.append(f"recipe step {i} ({step.describe()}) failed: {ex.error}")
                return Reached(False, "recipe", "; ".join(errors), ex)
        sig = state_signature(ex.observation)[0] if ex else None
        if ex and sig == recipe.expected_signature:
            return Reached(True, "recipe", None, ex)
        errors.append(f"recipe reached a different state ({sig} != {recipe.expected_signature})")
    return Reached(False, "recipe" if recipe.steps else "direct", "; ".join(errors) or "no setup recipe", None)
