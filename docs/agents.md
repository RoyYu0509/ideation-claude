# agents/ — 3-tier spawn topology & invariants

Full reference for the agent layer. Each agent's body holds its own operational rules;
read this file once for the shared architecture.

## Tier overview

```
L0 state machine (spec/research.js)
  ├─ spawnL1     → auto-research:orchestrator        — genuine multi-leaf fan-out
  │                   └─ spawns L2 leaves ('claude' / paper-polish-ar:*)
  ├─ spawnWorker → auto-research:producing-worker    — heavy single-owner roles
  │                   └─ serial leaf helpers (leaf-worker / Explore / Plan, one at a time)
  └─ spawnL2     → 'claude'                          — locked single-context leaf
```

## Which type holds the Agent (spawn) tool

| Type | Agent tool | Spawned by | Current roles |
|---|---|---|---|
| `auto-research:orchestrator` | ✓ | L0 (`spawnL1`) | ideation, review, rewrite, polish-figures; verifier when `audit.allow_spawn` is on |
| `auto-research:producing-worker` | ✓ | L0 (`spawnWorker`) | experiment + LITERATURE milestones (B1), seed→HANDOFF, rescue, amplify |
| `auto-research:leaf-worker` | ✗ | producing-worker; an orchestrator's goal-driven leaves | one bounded production / debug / investigation sub-task |
| `'claude'` (plain leaf) | ✓ (Tools:\*) | L0 (`spawnL2`) | single-context drafting, cross-check, read-only auditor leaves, lean verifier |

NOTE (DECISIONS.md §平台不变量验证史, CORRECTION 2026-06-25): the harness grants BOTH built-in
shells (`'claude'` and the catch-all) the full `Tools:*` set — **including Agent**. The old
"built-in shells can't nest" assumption is retracted. `'claude'` L2 leaves don't nest by
BEHAVIORAL contract (their goals never instruct a spawn), not by a structural lock.

The `spawn_guard.py` PreToolUse hook blocks the built-in catch-all worker type (deliberately
not named here — the keyword is scrubbed from every instruction surface; see the hook) as a
top-level backstop against unbounded nesting. `'claude'` stays unblocked ON PURPOSE — L0's own
L2 leaves are spawned as `'claude'`, so denying it would kill every legitimate `spawnL2` call.

## Invariants

1. **L0 owns ALL inter-phase transitions.** An L1 (orchestrator or producing-worker)
   returns at its role boundary — NEVER advances to the next phase or spawns a peer L1.

2. **Auditor ≠ producer.** The L0 independent verifier re-derives every number from disk;
   it is external and code-enforced. A producing-worker MUST NOT spawn an internal judge of
   its own result.

3. **No unbounded nesting.** leaf-worker carries NO Agent tool — structurally cannot nest.
   The `spawn_guard.py` hook is the additional harness-level backstop.

4. **producing-worker helpers are SERIAL.** One helper at a time, never a parallel swarm.
   Pass file paths, not bulk data. Spawn only `leaf-worker` / `Explore` / `Plan`.

5. **Gates are L0-only.** No L1 holds `AskUserQuestion`. Surface decisions via
   `escalations[]` in the return envelope; never block waiting on a human.

6. **Never alive while a science run executes.** Every science run fires DETACHED
   (`exp_ledger.py run-detach`); asyncRewake OS-waits at zero token cost. Never poll.

## Forbidden topologies

- `L0 → orchestrator → orchestrator` (peer L1 spawn — bypasses L0 gates and state persistence)
- `producing-worker → orchestrator` or `→ producing-worker` (nested heavy worker)
- `producing-worker → built-in catch-all` (carries Agent — hook-blocked)
- any worker spawning a judge of its own result (violates auditor ≠ producer)
