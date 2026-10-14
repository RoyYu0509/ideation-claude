#!/usr/bin/env bash
# t38 — LOOP FORWARD-MOTION guarantee (Phase-0 hardening, 2026-06-26). Three real bugs slipped through "32/32
# green" because NO test drove the research.js orchestration — it is an LLM-READ SPEC (AGENT()/spawn never run),
# so the suite's idiom is: FUNCTIONAL tests of the EXECUTABLE bin/ scripts + STATIC-STRUCTURAL grep on the spec.
# This file closes the gap for the forward-motion changes:
#   D1  — runResearchRescue spawned via a non-existent MODELS key (crash). Lock: config has models.rescue +
#         budgets.rescue, and the spawn is the FIXED role 'rescue' fanned out CONCURRENTLY (spawnWorkersParallel, §3), NOT a dynamic rescue-${...} template.
#   F1  — the FORWARD-FLOOR: when review wrote no HANDOFF, force an open major non-rewrite concern into a stub
#         BEFORE the `if (!handoffs.length) return` early-out, then re-scan (prose-convergence preserved).
#   F2  — the round-KEY bug: snapshot was keyed `loop_round` but the check keyed `loop_round` of the NEXT round
#         → the no-op backstop was DEAD. Lock the +1 alignment, the scaffold mint, and the NOOP failureSurface.
#   D2  — verify_final's ambition path: rescuable→loopback (no gate), not-rescuable→the UNIFIED terminal gate
#         (runTerminalGate(state,'over_claim'); the former ambition-residual gate was folded in). A gate with NO
#         matching ingest branch = a permanent ship-block (the dead-option bug) — assert BOTH exist + match.
#   D3  — a detached rescue is routed through onLongRun(state, env, 'RESCUE').
# (A) = FUNCTIONAL bin/reopen_noop_diff.sh ; (B) = STATIC spec/config invariants.  Run: bash tests/t38_loop_forward_motion.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
CFG="$ROOT/config/config.yaml"
NOOP="$ROOT/bin/reopen_noop_diff.sh"
pass=0; fail=0
chk(){ if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# (A) FUNCTIONAL — bin/reopen_noop_diff.sh: the deterministic no-op-reopen backstop (Seg 0.2, UNTESTED).
#     A temp ws with EXPERIMENTS/<seg>/result.md files; snapshot then check; the SHA-set fingerprint drives it.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
chk "noop script exists + executable"                 "test -x '$NOOP'"

WS="$(mktemp -d)"; trap 'rm -rf "$WS"' EXIT
mkdir -p "$WS/EXPERIMENTS/seg_a" "$WS/EXPERIMENTS/seg_b"
printf 'result A v1\n' > "$WS/EXPERIMENTS/seg_a/result.md"
printf 'result B v1\n' > "$WS/EXPERIMENTS/seg_b/result.md"

# round 1: snapshot, then check with NO change → NOOP
bash "$NOOP" snapshot "$WS" 1 >/dev/null 2>&1
chk "no change after snapshot → NOOP"                  "[ \"\$(bash '$NOOP' check '$WS' 1)\" = NOOP ]"

# round 2: snapshot, ADD a new result.md → PROGRESS (the additive-scaffold-filled case)
bash "$NOOP" snapshot "$WS" 2 >/dev/null 2>&1
mkdir -p "$WS/EXPERIMENTS/seg_c"; printf 'result C v1\n' > "$WS/EXPERIMENTS/seg_c/result.md"
chk "ADD a new result.md after snapshot → PROGRESS"   "[ \"\$(bash '$NOOP' check '$WS' 2)\" = PROGRESS ]"

# round 3: snapshot, CHANGE an existing result.md → PROGRESS (the redesign-re-authored case)
bash "$NOOP" snapshot "$WS" 3 >/dev/null 2>&1
printf 'result A v2 CHANGED\n' > "$WS/EXPERIMENTS/seg_a/result.md"
chk "CHANGE an existing result.md after snapshot → PROGRESS" "[ \"\$(bash '$NOOP' check '$WS' 3)\" = PROGRESS ]"

# round 4: snapshot, add only an EMPTY scaffold (.pending, NO result.md) → still NOOP (a scaffold contributes nothing)
bash "$NOOP" snapshot "$WS" 4 >/dev/null 2>&1
mkdir -p "$WS/EXPERIMENTS/seg_pending"; : > "$WS/EXPERIMENTS/seg_pending/.pending"
chk "empty scaffold (.pending, no result.md) added → still NOOP" "[ \"\$(bash '$NOOP' check '$WS' 4)\" = NOOP ]"

# round 99: check with NO snapshot for that round → PROGRESS (nothing re-opened ⇒ never a no-op)
chk "check with NO snapshot for the round → PROGRESS"  "[ \"\$(bash '$NOOP' check '$WS' 99)\" = PROGRESS ]"

# bad args → exit 2
chk "bad args (missing round) → exit 2"               "bash '$NOOP' check '$WS'; [ \$? -eq 2 ]"
chk "bad args (no args)       → exit 2"               "bash '$NOOP'; [ \$? -eq 2 ]"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# (B) STATIC-STRUCTURAL — each fixed invariant locked so a regression FAILs a test.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════

# ── D1: the rescue role is a FIXED, MODELS-resolvable key (the crash was a non-existent dynamic key) ──────
chk "config models: has a rescue: key"                "WS='$CFG' python3 - <<'PY'
import os,re,sys
src=open(os.environ['WS']).read().splitlines()
def has_key(section,key):
    inb=False
    for ln in src:
        if re.match(r'^%s:'%re.escape(section),ln): inb=True; continue
        if inb and re.match(r'^[A-Za-z_]',ln): inb=False
        if inb and re.match(r'^\s+%s:'%re.escape(key),ln): return True
    return False
sys.exit(0 if has_key('models','rescue') else 1)
PY"
chk "config budgets: has a rescue: key"               "WS='$CFG' python3 - <<'PY'
import os,re,sys
src=open(os.environ['WS']).read().splitlines()
def has_key(section,key):
    inb=False
    for ln in src:
        if re.match(r'^%s:'%re.escape(section),ln): inb=True; continue
        if inb and re.match(r'^[A-Za-z_]',ln): inb=False
        if inb and re.match(r'^\s+%s:'%re.escape(key),ln): return True
    return False
sys.exit(0 if has_key('budgets','rescue') else 1)
PY"
chk "runResearchRescue spawns the FIXED role 'rescue' (serial spawnWorker or concurrent spawnWorkersParallel)" "grep -qE \"spawnWorker(sParallel)?[(]'rescue'\" '$SPEC'"
chk "runResearchRescue fans out rescue workers CONCURRENTLY (spawnWorkersParallel, research-rescue §3)" "grep -qF \"spawnWorkersParallel('rescue'\" '$SPEC'"
chk "rescue spawn is NOT a dynamic rescue-\${...} template (D1 crash)" "! grep -qF 'rescue-\${' '$SPEC'"

# ── F1 forward-floor: force-forward block BEFORE `if (!handoffs.length) return`; major + skip needs:'spec' + re-scan ──
chk "F1 force-forward block precedes the early if(!handoffs.length)return" "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
f=src.find('F1 FORWARD-FLOOR'); e=src.find('if (!handoffs.length) return')
sys.exit(0 if (0 < f < e) else 1)
PY"
chk "F1 selects severity major"                        "grep -qF \"r.severity !== 'major'\" '$SPEC'"
chk "F1 skips needs === 'spec' (spec-convergence preserved; legacy 'rewrite' still tolerated)" "grep -qF \"r.needs === 'spec' || r.needs === 'rewrite'\" '$SPEC'"
chk "F1 re-scans handoffs after minting stubs"         "grep -qF 're-scan: stubs we just minted' '$SPEC'"

# ── F2 scaffold + the round-KEY alignment (the exact dead-backstop regression) ───────────────────────────
chk "F2 additive branch mints an EXPERIMENTS/ scaffold (.pending, no result.md)" "grep -qF 'EXPERIMENTS/\${seg}/.pending' '$SPEC'"
chk "F2 snapshot is keyed loop_round + 1 (NOT bare loop_round) — the dead-backstop fix" \
    "grep -qF 'reopen_noop_diff.sh\" snapshot \"\${ws}\" \"\${state.loop_round + 1}\"' '$SPEC'"
chk "F2 backstop: runExperiment calls reopen_noop_diff.sh check" "grep -qF 'reopen_noop_diff.sh\" check' '$SPEC'"
chk "F2 backstop: a NOOP fails-closed via failureSurface id noop-reopen-" "grep -qF 'noop-reopen-' '$SPEC'"

# ── D2: verify_final three-way partition + loopback(no gate)/failed(unified terminal gate) + reopenLoopWith + ingest ──
chk "D2 partition: inline_retained branch"             "grep -qF 'const inline_retained' '$SPEC'"
chk "D2 partition: loopback branch"                    "grep -qF 'const loopback ' '$SPEC'"
chk "D2 partition: failed branch"                      "grep -qF 'const failed ' '$SPEC'"
chk "D2 rescuable→loopback calls reopenLoopWith(state) with NO gate" "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find('if (loopback.length) {'); j=src.find('reopenLoopWith(state)', i)
seg=src[i:j]
# the loopback branch must reach reopenLoopWith without an intervening gate(state, ...) call
sys.exit(0 if (i>=0 and j>i and 'gate(state' not in seg) else 1)
PY"
chk "D2 reopenLoopWith is DEFINED"                     "grep -qF 'function reopenLoopWith(' '$SPEC'"
chk "D2 not-rescuable→runTerminalGate(state,'over_claim') (folded into the unified terminal gate)" "grep -qF \"runTerminalGate(state, 'over_claim')\" '$SPEC'"
chk "D2 the OLD ambition-residual gate + ingest are GONE (folded into terminal-gate-)"             "! grep -qF 'ambition-residual-' '$SPEC'"
chk "D2 MATCHING ingest branch id.startsWith('terminal-gate-')" "grep -qF \"id.startsWith('terminal-gate-')\" '$SPEC'"
chk "D2 unified ingest /ship/ path records ambition_reconciled: true (the ship-unblock)" "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
a=src.find(\"id.startsWith('terminal-gate-')\")
b=src.find(\"if (/rescue/i.test(c))\", a)        # end of the ship sub-branch
seg=src[a:b]
ok = ('/ship/i.test(c)' in seg) and ('ambition_reconciled: true' in seg)
sys.exit(0 if ok else 1)
PY"

# ── D3: a detached rescue is routed through onLongRun(state, env, 'RESCUE') ───────────────────────────────
chk "D3 detached rescue → onLongRun(state, env, 'RESCUE')" "grep -qF \"onLongRun(state, env, 'RESCUE')\" '$SPEC'"

# ── spec still parses ────────────────────────────────────────────────────────────────────────────────────
chk "spec parses (node --check)"                       "node --check '$SPEC'"

echo "----"; echo "t38_loop_forward_motion: $pass passed, $fail failed"; [ "$fail" = 0 ]
