#!/usr/bin/env python3
# auto-research — SPAWN GUARD (PreToolUse hook). See spawn_guard.sh for the wrapper.
#
# WHY THIS EXISTS (2026-06-25). A producing-worker (auto-research:producing-worker) may delegate PRODUCTION to
# helper subagents. The harness's built-in catch-all worker ('general-purpose') carries the full Tools:* set —
# the Agent (spawn) tool included — so such a helper can itself spawn more subagents, an UNBOUNDED, multi-layer
# nesting tree that burns tokens (the owner caught a single HANDOFF spawning a dozen+ nested searches before it
# produced anything). The structural fix is auto-research:leaf-worker: the SAME capabilities MINUS the Agent
# tool, so it does the production in one bounded context and structurally CANNOT nest.
#
# This hook is the harness-enforced backstop for that policy: even if some goal or model instinct reaches for
# the built-in catch-all worker, the spawn is DENIED here with a redirect to auto-research:leaf-worker. It does
# NOT touch any other spawn — auto-research:orchestrator / producing-worker / leaf-worker, plain 'claude'
# leaves, Explore, Plan, paper-polish-ar:* all pass straight through. Blast radius: exactly one subagent_type.
#
# Fails OPEN on an unparseable payload (the leaf-worker type + the scrubbed prompts are the primary guarantee;
# this guard must never wedge the pipeline). The deny path uses the same permissionDecision contract as
# ship_gate.py.
import json
import os
import subprocess
import sys

BLOCKED = "general-purpose"

REDIRECT = (
    "Spawning the built-in 'general-purpose' subagent is BLOCKED in auto-research. It carries the Agent tool, so "
    "it can recurse into an unbounded, multi-layer nested spawn tree — the token-burn this guard exists to "
    "prevent. Use subagent_type 'auto-research:leaf-worker' instead: it has the SAME capabilities "
    "(Read/Write/Edit/Bash/Grep/Glob/WebFetch/WebSearch/Skill) MINUS the spawn tool, so it does the production "
    "work in one bounded context and cannot nest."
    # NOTE: this denylist covers only 'general-purpose'. It is NOT the sole built-in that carries Agent —
    # 'claude' is Tools:* too (DECISIONS.md §平台不变量验证史 CORRECTION 2026-06-25). 'claude' stays UNBLOCKED
    # deliberately: L0 spawns its own L2 leaves as 'claude' (research.js spawnL2), so denying it would kill
    # every legitimate spawnL2 call; its no-nest guarantee is behavioral (L2 goals never instruct a spawn).
)


# ── L1 (2026-07-12): ideation-stage waiter/placeholder spawn guard ──────────────────
# WHY. The arxiv ideation stage (stage:"ideation") is enacted by a HEADLESS L1 subagent
# with NO self-rewake (spec/spawn-prompts/IDEATION-L0.md). Its ONLY correct fan-out is
# "one message, many Task calls, AWAITED IN-TURN". A 2026-07-12 run mis-reached for a
# "detached background fan-out + wait-for-notification" idiom that does not exist for
# Task/Agent — only the Bash tool has run_in_background. It fired judge batches it then
# could not collect, spawned a dozen+ no-op "noop-wait"/"placeholder" Task subagents to
# spin (pure token burn), and even FABRICATED verdicts to fill the gap it created. There
# is no structural "detached/background" field on a Task/Agent spawn, so the only
# observable signal for that specific abuse is the description text. We deny those
# waiter/placeholder spawns DURING ideation only. Every legitimate long-run in the
# pipeline (science via exp_ledger run-detach → Popen, prefetch → Bash run_in_background,
# probes → probe_run.sh) is a Bash call this Task|Agent hook never sees, and science runs
# happen in stage:"loop" anyway — so this deny cannot touch any real work. Fail-open.
WAITER_STAGES = {"ideation"}
WAITER_TOKENS = (
    "noop", "placeholder", "wait-for-notification", "wait for notification",
    "await background", "await notification", "spin while", "spinning while",
)
WAITER_REDIRECT = (
    "Spawning a no-op / placeholder 'waiter' subagent during the ideation stage is BLOCKED. "
    "You are a HEADLESS L1 subagent with NO self-rewake, so you cannot fire a batch 'in the "
    "background' and wait for a notification — Task/Agent have no run_in_background (only the "
    "Bash tool does). AWAIT every parallel judge/generate/screen/verify/recheck/refute Task "
    "batch WITHIN THIS TURN (one message, many Task calls), and read the resulting verdicts "
    "from the on-disk judge-cache / ideation-ledger via compute_gated_pool.py / "
    "ideation_ledger.py — never tally from memory and never spawn placeholder spinners."
)


def _read_stage(payload):
    """Read the current pipeline stage from state/pipeline-state.json (None if unreadable).
    Shared by log_spawn's C6 gate and the ideation waiter-deny; mirrors writer_isolation's
    tolerant lookup. Any failure returns None → callers treat it as 'no active run' and
    never deny on ambiguity (fail-open)."""
    try:
        d = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ""
        with open(os.path.join(d, "state", "pipeline-state.json")) as f:
            return (json.load(f) or {}).get("stage")
    except Exception:
        return None


def _deny(reason):
    """Emit the shared PreToolUse deny contract (identical across ship_gate/writer_isolation/
    spawn_guard) and exit. Only ever called once per invocation."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    sys.exit(0)


def log_spawn(payload, tool_input):
    """DETERMINISTIC ledger append (side-channel; fail-open). This PreToolUse hook fires for EVERY top-level
    Task/Agent spawn in EVERY session — including terminal-reopen resumes the L0's own `logEvent('agent_spawn')`
    side-channel (spec/research.js:128) skips. So we record the spawn boundary HERE, from the harness, tagged
    src:"hook" (the L0 record is tagged src:"l0"), giving run-events.jsonl a session-complete top-level spawn
    stream. Nested spawns the top-level hook never sees are covered by the native trace snapshot. Reuses the one
    sanctioned writer (bin/log_event.sh), which fills the ts/run_id/paper/round wrapper from pipeline-state.json;
    CLAUDE_PROJECT_DIR is injected in the hook context, so it lands in the right DATA_ROOT. Never touches stdout
    (the permissionDecision is the only thing on stdout) and never raises.
    C6 STAGE GATE: record ONLY while a run is ACTIVE — pipeline-state.json present AND stage != 'done'.
    Without this, every unrelated session in this cwd appends its spawns to run-events.jsonl under the
    FINISHED run's run_id (ledger pollution). A new run persists stage:'ideation' BEFORE its first spawn,
    so nothing legitimate is swallowed; the writer side stays untouched (it must still accept end-of-run
    events L0 emits at stage transitions)."""
    stage = _read_stage(payload)
    if not stage or stage == "done":
        return  # no readable active-run state -> no ledger append (the guard decision below is unaffected)
    try:
        rec = {
            "src": "hook",
            "subagent_type": str(tool_input.get("subagent_type") or "") or None,
            # P-3 fix (dossier 02, 2026-07-07): 9/97 leaf-worker spawns this run logged model=null because
            # tool_input.get("model") is empty whenever the caller relies on harness-side model inheritance
            # instead of passing `model` explicitly — the resolved tier then becomes recoverable only from the
            # (easily-pruned) native transcript. Fall back to a top-level `model` on the hook payload itself
            # (some harness versions surface the resolved model there even when tool_input omits it) before
            # accepting an honest None — never fabricate a value the hook cannot actually observe.
            "model": tool_input.get("model") or payload.get("model") or None,
            "description": (str(tool_input.get("description") or "")[:200]) or None,
            "parent_agent_type": payload.get("agent_type"),   # the CALLING agent (harness-provided when nested)
            "parent_agent_id": payload.get("agent_id"),
            "session_id": payload.get("session_id"),
        }
        le = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "log_event.sh")
        subprocess.run(["bash", le, "agent_spawn", json.dumps(rec, ensure_ascii=False)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        pass  # logging must NEVER wedge a spawn


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # unparseable -> allow; do not wedge the pipeline
    if (payload.get("tool_name") or "") not in ("Task", "Agent"):
        sys.exit(0)
    tool_input = payload.get("tool_input") or {}
    log_spawn(payload, tool_input)                     # deterministic ledger record BEFORE the deny decision
    subagent = str(tool_input.get("subagent_type") or "").strip().lower()
    if subagent == BLOCKED:
        _deny(REDIRECT)                                # unbounded-nesting guard (blast radius: one subagent_type)
    # L1: ideation-stage waiter/placeholder spawn deny. Stage-gated (only "ideation") AND
    # description-matched (the only observable signal — there is no structural detached bit).
    # Ambiguity (no readable stage) → _read_stage returns None → falls through to allow.
    desc = str(tool_input.get("description") or "").lower()
    if _read_stage(payload) in WAITER_STAGES and any(tok in desc for tok in WAITER_TOKENS):
        _deny(WAITER_REDIRECT)
    sys.exit(0)


if __name__ == "__main__":
    main()
