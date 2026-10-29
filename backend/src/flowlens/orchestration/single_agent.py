"""Single-agent baseline for evaluation (mode `single_agent`).

One agent identity and one continuing context do everything in sequence:
explore, design input cases for each form it found, judge the outcomes, and
choose the assertion for its own findings. Every prompt carries the agent's
notes from all earlier steps of the same review, so it sees its own previous
verdicts when it verifies (there is no separate verifier context).

What stays the same as the multi-agent modes, for a fair comparison: the same
model, requirements, task instructions, typed actions and assertions, budgets,
fresh browser contexts and workspaces for every test case and replay, and code
evaluation of assertions. Its outcomes are recorded with
`verification_independence = "self"`, never as independent verification.

The sequential `explore_test_verify` mode is NOT this baseline: it already uses
separate specialist contexts and an independent verifier.
"""

from __future__ import annotations

from flowlens.orchestration.review import ReviewRun

AGENT = "single-agent"
NOTES_KEPT = 14

SOLO_SYSTEM = (
    "You are the single FlowLens agent reviewing an authorised test website end to end. You alone explore it, "
    "design input tests for forms you find, judge the outcomes, and choose the verification assertion for your "
    "own suspected defects. Code executes browser actions in fresh sessions and evaluates assertions. "
    "Your notes from earlier steps of this same review are included in every step."
)


class SingleAgentRun(ReviewRun):
    explorer_id = AGENT
    tester_id = AGENT
    verifier_id = AGENT
    independent_verification = False
    explorer_name = "the single agent, now exploring"

    def __init__(self, run, store, settings, llm):
        super().__init__(run, store, settings, llm)
        self.notes: list[str] = []
        self.explore_context_id = f"{AGENT}:explore"

    @property
    def explorer_reserve(self) -> int:
        # Same split as the shared-queue mode: exploration leaves testing and verification capacity.
        lim = self.run.limits
        return lim.reserved_testing_calls + lim.reserved_verification_calls

    def explore_cookies(self) -> list[dict]:
        """Explore in a fresh workspace, like the queue explorers, so starting data match."""
        ctx = self.provider.provision(self.origin, f"{AGENT}:explore")
        self.explore_context_id = ctx.context_id
        return ctx.cookies

    async def call_model(self, messages, *, agent_id, phase, task, **kw):
        notes = "\n".join(self.notes[-NOTES_KEPT:]) or "(none yet)"
        merged = [
            {"role": "system", "content": f"{SOLO_SYSTEM}\n\nInstructions for this step:\n{messages[0]['content']}"},
            {"role": "user", "content": f"Your notes from earlier in this review:\n{notes}\n\n{messages[-1]['content']}"},
        ]
        content, mc_id = await super().call_model(merged, agent_id=AGENT, phase=phase, task=task, **kw)
        self.notes.append(f"[{phase}] {' '.join(content.split())[:260]}")
        return content, mc_id
