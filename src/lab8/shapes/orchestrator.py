"""Shape C — orchestrator plus read-only investigators.

1. The orchestrator reads the claim view and builds a typed handoff with
   `lab8.handoff.make_handoff`. Allowed tools are read-only. Facts are empty: the
   orchestrator does not forward parent_secret, raw headers, the ticket, or the claim row.
2. `lab8.runtime.run_readonly_investigators` runs those tools (worker=True, no write registry).
3. The orchestrator quotes from the investigator's allowlisted order view with
   `compute_compensation` and is the only caller of `durability.issue_refund`.
   It passes the FULL quote; the host subtracts earlier refunds on the same order.
4. The trace records the sanitized handoff and allowlisted investigator results,
   never the parent context.

An LLM summary of the parent context is not a sanitizer; the allowlist in
`lab8.handoff` is.

Self-contained: the hidden grader copies only the three shape files.
"""

from __future__ import annotations

import sqlite3

from lab8 import durability
from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.handoff import HandoffError, make_handoff
from lab8.mock_llm import complete
from lab8.runtime import ToolRejected, run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "orchestrator"
INVESTIGATOR_TOOLS = ["lookup_order", "lookup_refund_history", "lookup_policy"]


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

    # Orchestrator: triage on the allowlisted claim view.
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim.get("found"):
        trace.add("triage", {"found": False})
        return done("failed", 0, "unknown_claim")
    complete(budget, seed=seed, purpose="plan", prompt=f"triage claim {claim_id}")
    trace.add("triage", {"found": True, "has_order_id": bool(claim.get("order_id"))})
    if not claim.get("order_id"):
        complete(budget, seed=seed, purpose="draft", prompt="needs_info")
        return done("needs_info", 0, "missing_order_id")

    # Typed handoff: allowlist only, read-only tools, no facts copied from the parent.
    try:
        handoff = make_handoff(
            request_id=f"REQ-{claim_id}",
            claim_id=claim_id,
            task="verify_order_and_refund_history",
            facts={},
            allowed_tools=list(INVESTIGATOR_TOOLS),
        )
    except HandoffError as exc:
        trace.add("handoff_rejected", {"error": str(exc)})
        return done("failed", 0, "handoff_rejected")
    trace.add("handoff", safe_dump(handoff))

    try:
        investigated = run_readonly_investigators(conn, budget, handoff, principal_id=claim["principal_id"])
    except ToolRejected as exc:
        trace.add("investigator_rejected", {"error": str(exc)})
        return done("failed", 0, "tool_rejected")
    complete(budget, seed=seed, purpose="investigate", prompt=handoff["task"])

    tools = investigated["tools"]
    order_view = tools.get("lookup_order") or {}
    history = tools.get("lookup_refund_history") or {}
    trace.add(
        "investigator",
        {
            "lookup_order": safe_dump(order_view),
            "refund_history": {"refund_count": history.get("refund_count"), "refunded_vnd": history.get("refunded_vnd")},
            "policy_count": len((tools.get("lookup_policy") or {}).get("policies") or []),
        },
    )
    if not order_view.get("visible"):
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        return done("escalated", 0, order_view.get("reason"))

    # Orchestrator owns the money: quote in code from the structured order view.
    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order_view["order"])
    proposal = int(quote["amount_vnd"])
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
