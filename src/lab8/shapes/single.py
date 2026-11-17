"""Shape B — one ReAct agent.

Uses `lab8.runtime.run_react` with max_steps=8. The agent (`decide`) may only pick
read tools; `run_react` runs it with worker=True so any write tool is rejected.
After the loop, the shape — not the model — validates the gathered facts and calls
`durability.issue_refund`, the only writer.

Ticket text is untrusted user data. `decide` never reads delay numbers, clause ids,
or order ids out of the ticket: the order row from `lookup_order` is the source of
truth and the quote comes from `compute_compensation`.

Per-order cap: `lookup_refund_history` is read for context, but the FULL quote is
passed to `durability.issue_refund`; the host subtracts earlier refunds itself.

Each `decide` call is one simulated model call (MockLLM) counted in the Budget, so
cost stays comparable with the other shapes.

The trace records tool names and allowlisted results only (no ticket, no
principal_id, no raw claim/order row).

Self-contained: the hidden grader copies only the three shape files.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8 import durability
from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.mock_llm import complete
from lab8.runtime import ToolRejected, run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


class _Agent:
    """ReAct policy. Keeps its own scratchpad because run_react only echoes the last tool."""

    def __init__(self, claim_id: str, seed: int, budget: Budget, trace: Trace) -> None:
        self.claim_id = claim_id
        self.seed = seed
        self.budget = budget
        self.trace = trace
        self.memory: dict[str, Any] = {}

    def __call__(self, seen: dict[str, Any]) -> dict[str, Any]:
        last_tool = seen.get("last_tool")
        if last_tool:
            self.memory[last_tool] = seen.get("last_result") or {}
        action = self._next_action()
        # Simulated model call for this reasoning step. Prompt = tool name only,
        # so no ticket text or personal data is sent anywhere.
        label = action.get("tool") or f"final:{action['final']['status']}"
        complete(self.budget, seed=self.seed, purpose="react_step", prompt=label)
        self.trace.add("react_step", {"action": label})
        return action

    def _next_action(self) -> dict[str, Any]:
        mem = self.memory
        if "get_claim_view" not in mem:
            return {"tool": "get_claim_view", "args": {"claim_id": self.claim_id}}
        claim = mem["get_claim_view"]
        if not claim.get("found"):
            return {"final": {"status": "failed", "error_reason": "unknown_claim"}}
        if not claim.get("order_id"):
            return {"final": {"status": "needs_info", "error_reason": "missing_order_id"}}
        scope = {"order_id": claim["order_id"], "principal_id": claim["principal_id"]}
        if "lookup_order" not in mem:
            return {"tool": "lookup_order", "args": scope}
        order_view = mem["lookup_order"]
        if not order_view.get("visible"):
            return {"final": {"status": "escalated", "error_reason": order_view.get("reason")}}
        if "lookup_refund_history" not in mem:
            return {"tool": "lookup_refund_history", "args": scope}
        if "compute_compensation" not in mem:
            return {"tool": "compute_compensation", "args": {"order": order_view["order"]}}
        return {"final": {"status": "quoted"}}


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))

    def done(status: str, proposal: int, reason: str | None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": int(proposal), "reason": reason})
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    agent = _Agent(claim_id, seed, budget, trace)
    try:
        loop = run_react(
            conn,
            budget,
            observation={"claim": {"claim_id": claim_id}},
            decide=agent,
            max_steps=MAX_STEPS,
            worker=True,
        )
    except ToolRejected as exc:
        trace.add("tool_rejected", {"error": str(exc)})
        return done("failed", 0, "tool_rejected")

    final = loop["final"]
    trace.add("react_stop", {"stopped": loop["stopped"], "status": final.get("status")})
    if loop["stopped"] == "step_cap":
        return done("failed", 0, "step_cap")
    if final.get("status") != "quoted":
        status = final.get("status", "failed")
        if status not in ("failed", "needs_info", "escalated"):
            status = "failed"
        complete(budget, seed=seed, purpose="draft", prompt=status)
        return done(status, 0, final.get("error_reason"))

    # Code, not the model, owns the money from here on.
    mem = agent.memory
    order = mem["lookup_order"]["order"]
    history = mem.get("lookup_refund_history") or {}
    quote = mem["compute_compensation"]
    proposal = int(quote["amount_vnd"])
    trace.add("order", safe_dump(order))
    trace.add("refund_history", {"refund_count": history.get("refund_count"), "refunded_vnd": history.get("refunded_vnd")})
    trace.add("quote", safe_dump(quote))

    if proposal <= 0:
        complete(budget, seed=seed, purpose="draft", prompt="denied")
        return done("denied", 0, quote.get("reason"))

    try:
        outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    trace.add("issue_refund", {"ok": bool(outcome["ok"]), "reason": outcome["reason"], "conflict": bool(outcome["conflict"])})

    complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")
    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        return done(status, proposal, outcome["reason"])
    return done("resolved", proposal, None)
