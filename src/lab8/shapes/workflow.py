"""Shape A — deterministic workflow.

Signature (do not change):

    run_claim(claim_id, *, seed, store_path, crash_at=None) -> RunResult

Fixed Python steps. Money stays in code (`lab8.tools.compute_compensation`).

1. Open the store. Read the claim through `get_claim_view` (not SELECT *).
2. Missing order_id -> status `needs_info`. Do not write the ledger.
3. `lookup_order`. If not visible -> `escalated`. Do not copy phone, address, item, internal note.
4. Quote from the order row. Ignore delay numbers written in the ticket.
5. Quote amount 0 -> `denied`. Do not call issue_refund.
6. Quote amount > 0 -> `durability.issue_refund(conn, claim_id, <full quote>)`.
   The host checks approval and subtracts earlier refunds on the same order.
   Auth failure or order already refunded -> `denied` (host writes `policy_denied`).
   `proposal_amount` stays the full quote. Amount conflict -> `failed`.
7. Success -> `resolved`. One ledger row, one `refund_committed` audit.
8. MockLLM only drafts the reply text. It never sees the money decision.

What the trace deliberately does NOT contain: the ticket text, principal_id,
parent_secret, raw headers, or any raw order row (phone, address, item,
internal note). Only allowlisted views from `lookup_order` / `compute_compensation`
and host outcome reasons are written.

This file is self-contained on purpose: the hidden grader copies only the three
shape files from the group repo, so it only imports official `lab8` modules.
"""

from __future__ import annotations

import sqlite3

from lab8 import durability
from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.mock_llm import complete
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, lookup_order, tool_cost
from lab8.trace import Trace

SHAPE = "workflow"


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

    # Step 1: claim view (allowlisted columns only).
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim.get("found"):
        trace.add("step", {"name": "get_claim_view", "found": False})
        return done("failed", 0, "unknown_claim")
    trace.add("step", {"name": "get_claim_view", "found": True, "has_order_id": bool(claim.get("order_id"))})

    # Step 2: no order id -> ask for it. Never mine an order id from ticket text.
    if not claim.get("order_id"):
        complete(budget, seed=seed, purpose="draft", prompt="needs_info")
        return done("needs_info", 0, "missing_order_id")

    # Step 3: ownership-scoped order lookup.
    budget.add_tool(tool_cost())
    order_view = lookup_order(conn, claim["order_id"], claim["principal_id"])
    if not order_view.get("visible"):
        trace.add("step", {"name": "lookup_order", "visible": False, "reason": order_view.get("reason")})
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        return done("escalated", 0, order_view.get("reason"))
    order = order_view["order"]
    trace.add("step", {"name": "lookup_order", "visible": True, "order": safe_dump(order)})

    # Step 4: quote from the structured order row and current policy only.
    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order)
    proposal = int(quote["amount_vnd"])
    trace.add("quote", safe_dump(quote))

    # Step 5: nothing owed -> deny without touching the host write path.
    if proposal <= 0:
        complete(budget, seed=seed, purpose="draft", prompt="denied")
        return done("denied", 0, quote.get("reason"))

    # Step 6: host gate. Full quote in; host applies approval + per-order cap.
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
    # Step 7.
    return done("resolved", proposal, None)
