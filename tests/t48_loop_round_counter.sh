#!/usr/bin/env bash
# t48 — LOOP ROUND-COUNTER timing (FIX B, P1#5: the loop_round off-by-one at the between-rounds gate). Same idiom as
# t38/t40: research.js is an LLM-READ SPEC (AGENT()/spawn never run), so the suite is STATIC-STRUCTURAL grep + a
# python ordering check on the spec. THE BUG: the increment was a pre-increment lazily DEFERRED to the next 'loop'
# re-entry, gated on round_in_progress — but round_in_progress is cleared right after B3, BEFORE the between-rounds
# work (maybeAmplify → generateHandoff(state,true) re-authors round N+1 + reopens experiments → the handoff gate
# ENDS THE TURN). So while paused at the round-(N+1) work-order gate, pipeline-state.json.loop_round still read N and
# gateHandoffApproval labeled the card with the stale N. THE FIX: beginNextRound advances the counter (loop_round+=1,
# round_in_progress=true, round_baseline_paper re-anchor) at the CONTINUE / amplify-raised transition — AFTER
# generateHandoff(state,true) (which still needs the OLD loop_round for its reopen_noop_diff snapshot key loop_round+1
# and its round-N commit messages) and BEFORE state.stage='handoff_gate' — so the gate + persisted state carry N+1.
# The 'loop' re-entry guard (if !round_in_progress) then SKIPS re-incrementing, preserving the idempotency invariant
# (a resume/re-present while paused at the gate never double-counts).
#   Run: bash tests/t48_loop_round_counter.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
pass=0; fail=0
chk(){ if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── the beginNextRound primitive is DEFINED and advances the counter + arms round_in_progress + re-anchors baseline ─
chk "beginNextRound(state) is DEFINED"                    "grep -qF 'function beginNextRound(state) {' '$SPEC'"
chk "beginNextRound increments loop_round + arms round_in_progress (in the fn body)" "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.index('function beginNextRound(state) {'); body=src[i:src.index('\n}', i)]
ok = ('state.loop_round += 1' in body) and ('state.round_in_progress = true' in body)
sys.exit(0 if ok else 1)
PY"
chk "beginNextRound re-anchors round_baseline_paper"     "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.index('function beginNextRound(state) {'); body=src[i:src.index('\n}', i)]
sys.exit(0 if 'state.round_baseline_paper =' in body else 1)
PY"

# ── the CORE FIX: at EVERY between-rounds gate transition in case 'loop', the counter is pre-incremented — i.e.
#    generateHandoff(state, true) … beginNextRound(state) … 'handoff_gate' in source order (N+1 reaches the gate) ──
chk "both loop transitions pre-increment: generateHandoff(state,true) → beginNextRound(state) → 'handoff_gate'" \
    "S='$SPEC' python3 - <<'PY'
import os,re,sys
src=open(os.environ['S']).read()
lo=src.index(\"case 'loop': {\"); hi=src.index(\"case 'verify_final': {\", lo)
blk=src[lo:hi]
gates=[m.start() for m in re.finditer(r\"handoff_approval \\? 'handoff_gate'\", blk)]
assert len(gates)==2, ('want 2 between-rounds gates in case loop, found', len(gates))
for g in gates:
    pre=blk[:g]
    b=pre.rindex('beginNextRound(state)')            # the pre-increment
    h=pre.rindex('generateHandoff(state, true)')     # runs first (keeps the OLD loop_round for its snapshot key)
    assert h < b < g, (h,b,g)
sys.exit(0)
PY"
chk "beginNextRound is CALLED exactly three times (the two loop transitions + the terminal card's Amplify)" \
    "[ \"\$(grep -cF 'beginNextRound(state)' '$SPEC')\" = 4 ]"   # 1 definition line + 2 loop call sites + 1 terminal-gate Amplify ingest (2026-09-12; same generateHandoff(true) → beginNextRound → handoff_gate order, locked in t79)

# ── IDEMPOTENCY preserved: the loop-top increment stays GUARDED on !round_in_progress (so a resume/re-present at the
#    gate — where beginNextRound already set round_in_progress=true — SKIPS re-incrementing, never double-counts) ──
chk "loop-top increment still guarded by if (!state.round_in_progress)" "grep -qF 'if (!state.round_in_progress) {' '$SPEC'"
chk "loop-top guard body still does the loop_round += 1 (round 1 + reopen/detach-rewake re-entries)" "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.index('if (!state.round_in_progress) {'); body=src[i:src.index('}', i)]
sys.exit(0 if 'state.loop_round += 1' in body else 1)
PY"

# ── the gate report's raisedThisRound was re-based onto the just-completed round N = loop_round-1 (the amplifier that
#    raised the target ran there); without this, the N+1 gate would wrongly report the amplifier as not-raised ──
chk "gate raisedThisRound compares raised_at_round to loop_round - 1 (the earning round)" \
    "grep -qF 'raised_at_round === state.loop_round - 1' '$SPEC'"

# ── [neg] removing the beginNextRound call sites re-introduces the off-by-one → the ordering assert FAILs ───────────
SPB="$(mktemp)"; grep -vF 'beginNextRound(state)' "$SPEC" > "$SPB"
chk "[neg] ordering assert FAILs if the beginNextRound pre-increment is removed" "S='$SPB' python3 - <<'PY'
import os,re,sys
src=open(os.environ['S']).read()
lo=src.index(\"case 'loop': {\"); hi=src.index(\"case 'verify_final': {\", lo); blk=src[lo:hi]
gates=[m.start() for m in re.finditer(r\"handoff_approval \\? 'handoff_gate'\", blk)]
try:
    for g in gates: blk[:g].rindex('beginNextRound(state)')
    sys.exit(1)          # still found → strip failed → the [neg] guard would be meaningless → this test FAILs
except ValueError:
    sys.exit(0)          # not found → the ordering assert correctly FAILs on the stripped spec → [neg] PASSes
PY"
rm -f "$SPB"

# ── spec still parses ────────────────────────────────────────────────────────────────────────────────────────────
chk "spec parses (node --check)"                         "node --check '$SPEC'"

echo "----"; echo "t48_loop_round_counter: $pass passed, $fail failed"; [ "$fail" = 0 ]
