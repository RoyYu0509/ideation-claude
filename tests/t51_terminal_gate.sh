#!/usr/bin/env bash
# t51 — the UNIFIED TERMINAL GATE + negative-abandon (P3#13, 2026-07-01). At every non-clean terminal exit
# (cap_exit / negative_result / over_claim) L0 SURFACES ONE owner gate {Abandon / Ship / Rescue-one-more-round};
# a clean-earned EXIT still auto-ships. The verifier emits the routing signal (central_claim.alive + how_it_failed)
# and pre-writes .terminal-verdict.json; runVerify routes; runTerminalGate surfaces (NO leaf spawn); the unified
# terminal-gate- ingest disposes. The former ambition-residual gate is FOLDED IN; there is NO terminal_verdict leaf.
#
# research.js is an LLM-READ SPEC (AGENT()/spawn never run), so the suite idiom is STATIC-STRUCTURAL greps on the
# spec + FUNCTIONAL fixture runs of the executable bin/ + hooks. (A)=STATIC spec/asset invariants; (B)=FUNCTIONAL
# ship_gate.py / pipeline_status.sh / loop_gate.sh fixtures.  Run: bash tests/t51_terminal_gate.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
VERIFY="$ROOT/spec/spawn-prompts/VERIFY-PROTOCOL.md"
REVIEWC="$ROOT/spec/spawn-prompts/REVIEW-L0-CONTRACT.md"
REFRAME="$ROOT/plugins/paper-polish-ar/skills/reframe-result/SKILL.md"
CFG="$ROOT/config/config.yaml"
GATE="$ROOT/bin/loop_gate.sh"
STATUS="$ROOT/bin/pipeline_status.sh"
SHIPHOOK="$ROOT/hooks/ship_gate.py"
pass=0; fail=0
chk(){ if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# (A) STATIC-STRUCTURAL — the spec/asset invariants of the unified terminal gate.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════

# ── #1 cap routing: loop tail sets terminal_reason (cap_exit vs clean_exit); BOTH go to verify_final; the old
#      max_loop_rounds_unresolved auto-ship string is GONE. ────────────────────────────────────────────────────
chk "#1 loop tail sets terminal_reason cap_exit vs clean_exit" "grep -qF \"state.terminal_reason = (verdict === 'EXIT_AT_CAP') ? 'cap_exit' : 'clean_exit'\" '$SPEC'"
chk "#1 clean EXIT still sets ship_reason=clean_exit"          "grep -qF \"if (verdict === 'EXIT') state.ship_reason = 'clean_exit'\" '$SPEC'"
chk "#1 BOTH exits route to verify_final (persisted first)"    "grep -qF \"state.stage = 'verify_final'; persist(state); break\" '$SPEC'"
chk "#1 removed max_loop_rounds_unresolved auto-ship string GONE" "! grep -qF 'max_loop_rounds_unresolved' '$SPEC'"

# ── #2 negative routing: runVerify reads central_claim / cc.alive===false → runTerminalGate('negative_result'),
#      with NO recordStage('verify_final') between the verdict!=='PASS' check and that negative return. ──────────
chk "#2 runVerify reads env.metrics.central_claim into cc"     "grep -qF 'const cc = (env.metrics && env.metrics.central_claim) || null' '$SPEC'"
chk "#2 dead-claim branch guards cc.alive === false"          "grep -qF 'if (cc && cc.alive === false) {' '$SPEC'"
chk "#2 dead claim routes to runTerminalGate(state,'negative_result')" "grep -qF \"runTerminalGate(state, 'negative_result')\" '$SPEC'"
chk "#2 the dead-claim route PRECEDES any verify_final recordStage (HOLLOW/PASS ordering)" "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
p=src.find(\"if (verdict !== 'PASS') {\")               # the PASS check (must run FIRST)
n=src.find(\"return runTerminalGate(state, 'negative_result')\")
# the negative route exists, comes after the PASS check, and NO verify_final recordStage sits between them
ok = (0 < p < n) and (\"recordStage(state, 'verify_final'\" not in src[p:n])
sys.exit(0 if ok else 1)
PY"

# ── #3 cap-after-verify routing: the reconciled-success path checks terminal_reason==='cap_exit' →
#      runTerminalGate('cap_exit') BEFORE the clean recordStage; else clean path records verify_final PASS. ─────
chk "#3 reconciled-success path checks terminal_reason==='cap_exit'" "grep -qF \"if (state.terminal_reason === 'cap_exit') {\" '$SPEC'"
chk "#3 cap route → runTerminalGate(state,'cap_exit')"        "grep -qF \"runTerminalGate(state, 'cap_exit')\" '$SPEC'"
chk "#3 cap check PRECEDES the clean recordStage (const reconciledFinal)" "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
c=src.find(\"if (state.terminal_reason === 'cap_exit') {\")
f=src.find('const reconciledFinal = reconciled0')
sys.exit(0 if (0 < c < f) else 1)
PY"
chk "#3 clean path still records verify_final PASS w/ reconciledFinal" "grep -qF 'ambition_reconciled: reconciledFinal' '$SPEC'"
chk "#3 verify_final stage advances to spec_freeze on PASS" "grep -qF \"state.stage = 'spec_freeze'; persist(state); break\" '$SPEC'"

# ── #4 over_claim fold: the not-reconciled path calls runTerminalGate('over_claim'); the OLD ambition-residual
#      gate + ingest are GONE; the unified terminal-gate- ingest exists with abandon/ship/rescue branches. ───────
chk "#4 not-rescuable → runTerminalGate(state,'over_claim')"  "grep -qF \"runTerminalGate(state, 'over_claim')\" '$SPEC'"
chk "#4 OLD ambition-residual gate+ingest GONE (folded)"      "! grep -qF 'ambition-residual-' '$SPEC'"
chk "#4 unified ingest branch id.startsWith('terminal-gate-')" "grep -qF \"id.startsWith('terminal-gate-')\" '$SPEC'"
chk "#4 unified ingest has abandon/ship/rescue branches"      "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
a=src.find(\"id.startsWith('terminal-gate-')\")
# bound the ingest branch: up to the next top-level ingest 'if (id.startsWith(' or the applyPickedIdea def
b=src.find('function applyPickedIdea', a)
seg=src[a:b if b>a else a+4000]
ok = all(t in seg for t in ('/abandon/i.test(c)','/ship/i.test(c)','/rescue/i.test(c)'))
sys.exit(0 if ok else 1)
PY"

# ── runTerminalGate is a SOURCE-DERIVED gate with NO leaf spawn; FAIL-OPEN; terminal_reason persisted BEFORE gate() ──
chk "runTerminalGate is DEFINED"                              "grep -qF 'function runTerminalGate(state, reason)' '$SPEC'"
chk "runTerminalGate spawns NOTHING (no leaf / no AGENT)"     "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find('function runTerminalGate(state, reason)')
j=src.find('\n}', i)
seg=src[i:j]
ok = all(t not in seg for t in ('spawnL1(','spawnL2(','spawnWorker(','spawnAgent(','AGENT('))
sys.exit(0 if ok else 1)
PY"
chk "runTerminalGate is FAIL-OPEN on .terminal-verdict.json"  "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find('function runTerminalGate(state, reason)'); j=src.find('\n}', i); seg=src[i:j]
ok = ('.terminal-verdict.json' in seg) and ('try {' in seg) and ('catch' in seg) and ('if (!tv)' in seg)
sys.exit(0 if ok else 1)
PY"
chk "runTerminalGate persists terminal_reason BEFORE gate()"  "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find('function runTerminalGate(state, reason)'); j=src.find('\n}', i); seg=src[i:j]
p=seg.find('state.terminal_reason = reason; persist(state)'); g=seg.find('gate(state,')
sys.exit(0 if (0 <= p < g) else 1)
PY"

# ── the terminal_verdict LEAF is DROPPED per the refinement — no role/rubric/config line exists ─────────────────
chk "NO terminal_verdict role/config token anywhere in spec/config" "! grep -rqiF 'terminal_verdict' '$ROOT/spec' '$ROOT/config'"
chk "NO TERMINAL-VERDICT.md spawn-prompt asset"              "! test -f '$ROOT/spec/spawn-prompts/TERMINAL-VERDICT.md'"

# ── #8 reframe restriction across VERIFY-PROTOCOL / reframe-result / REVIEW-L0-CONTRACT ─────────────────────────
chk "#8 VERIFY-PROTOCOL: a novelty-contradicting negative is NOT a deliverable" "grep -qF 'NEGATIVE_CONTRADICTS_NOVELTY' '$VERIFY' && grep -qF 'THIS IS NOT A CONTRIBUTION AND NOT A DELIVERABLE' '$VERIFY'"
chk "#8 VERIFY-PROTOCOL: that verdict is never a green light (routes to the terminal gate)" "grep -qF 'It is NEVER a green light' '$VERIFY' && grep -qF 'the recommended disposition is ABANDON' '$VERIFY'"
chk "#8 no 'legitimate deliverable' licence survives anywhere in the negative-result policy" "! grep -rqiF 'legitimate deliverable' '$ROOT/spec' '$ROOT/skills' '$ROOT/assets'"
chk "#8 VERIFY-PROTOCOL: central_claim + how_it_failed emitted"     "grep -qF 'metrics.central_claim' '$VERIFY' && grep -qF 'metrics.how_it_failed' '$VERIFY'"
chk "#8 VERIFY-PROTOCOL: alive=false BINDING RULE stated"           "grep -qF 'alive=false IFF' '$VERIFY'"
chk "#8 reframe-result: narrows a REAL result / dead claim MUST NOT repackage" "grep -qF 'central claim is DEAD' '$REFRAME' && grep -qF 'MUST NOT repackage' '$REFRAME'"
chk "#8 REVIEW-L0-CONTRACT: never launder a dead central claim"     "grep -qF 'never launder a dead central claim into a positive' '$REVIEWC'"

# ── #8b the terminal-Ship steering marker is CONSUMED (P3#13 CONFIRMED-2 fix; spec re-aim 2026-08-30:
#      consumption moved to spec_freeze — the ONE terminal stage). specFreezeGoal passes
#      .terminal-narrowing-accepted.md as <TERMINAL_STEER> (exists()-guarded thin POINTER); SPEC-FREEZE.md §4
#      carries the OBEY semantics (owner override on a dead claim: stated AS an override, never repackaged /
#      over-claim: narrow to the evidence / cap exit: deliver as-is with the unresolved items listed). ─
chk "#8b specFreezeGoal CONSUMES the terminal-Ship steering marker (no longer inert)" "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find('function specFreezeGoal(ws, venue)')
j=src.find('\nfunction ', i+1)              # bound to the specFreezeGoal body
seg=src[i:j if j>i else i+3000]
ok = ('.terminal-narrowing-accepted.md' in seg) and ('exists(steer)' in seg) and ('TERMINAL_STEER' in seg)
sys.exit(0 if ok else 1)
PY"
chk "#8b the marker consumption is a thin POINTER (rubric carries the OBEY semantics, not inlined prose)" "grep -qF 'Read that file and obey it' '$ROOT/spec/spawn-prompts/SPEC-FREEZE.md'"

# ── #9 the whole spec still parses ─────────────────────────────────────────────────────────────────────────────
chk "#9 spec parses (node --check)"                          "node --check '$SPEC'"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# (B) FUNCTIONAL fixtures — the executable oracles the ingest routes to.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
gitq() { git -c user.email=t@t.t -c user.name=t -C "$1" "${@:2}" >/dev/null 2>&1; }
mk_git_ws(){ local ws="$1"; mkdir -p "$ws/paper" "$ws/code"
  for d in "$ws" "$ws/paper" "$ws/code"; do gitq "$d" init; gitq "$d" commit --allow-empty -m base; done; }
mk_backbone(){ local ws="$1"; mkdir -p "$ws/EXPERIMENTS/ENV_READY" "$ws/REVIEW" "$ws/SPEC"
  echo x > "$ws/HANDOFF.md"; echo x > "$ws/EXPERIMENTS/results_master.json"
  echo x > "$ws/SPEC/SPEC-v0.md"; echo x > "$ws/SPEC-FINAL.md"; echo x > "$ws/REVIEW/round1_reviews.md"; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# ── #5 ABANDON fixture: hooks/ship_gate.py ALLOWs a FINAL-REPORT-killed.md write in an EMPTY-ledger workspace
#      (its basename is NOT the hook-gated FINAL-REPORT.md), while FINAL-REPORT.md in that same empty ws is DENIED. ─
WS5="$TMP/runs/killed"; mk_git_ws "$WS5"
echo '{"schema":"auto-research-milestone@1","paper_slug":"killed","stages":{}}' > "$WS5/milestone-state.json"  # empty finishing ledger
shiprun(){ CLAUDE_PLUGIN_ROOT="$ROOT" CLAUDE_PROJECT_DIR="$TMP" python3 - "$SHIPHOOK" "$1" <<'PY'
import sys, json, subprocess
hook, fp = sys.argv[1], sys.argv[2]
payload = {"tool_name":"Write","tool_input":{"file_path":fp,"content":"x"}}
p = subprocess.run(["python3",hook], input=json.dumps(payload), text=True, capture_output=True)
sys.stdout.write(p.stdout)
PY
}
denied(){ printf '%s' "$1" | grep -q '"permissionDecision": *"deny"'; }
# direct conditionals (NOT chk/eval) — the deny JSON carries double-quotes that would break an eval string.
out5k="$(shiprun "$WS5/FINAL-REPORT-killed.md")"
if [ -z "$out5k" ]; then echo "PASS  #5 ship_gate ALLOWs FINAL-REPORT-killed.md (empty-ledger abandon)"; pass=$((pass+1)); else echo "FAIL  #5 ship_gate ALLOWs FINAL-REPORT-killed.md (out=$out5k)"; fail=$((fail+1)); fi
out5s="$(shiprun "$WS5/FINAL-REPORT.md")"
if denied "$out5s"; then echo "PASS  #5 ship_gate DENIEs FINAL-REPORT.md in the same empty-ledger ws (contrast)"; pass=$((pass+1)); else echo "FAIL  #5 ship_gate DENIEs FINAL-REPORT.md contrast (out=$out5s)"; fail=$((fail+1)); fi

# ── #6 SHIP fixture: after the owner elects Ship the ingest records verify_final ambition_reconciled:true; the
#      pipeline_status oracle then reads reconciled:true (+ all finishing stages @ real commits) → SHIP_READY yes. ─
WS6="$TMP/runs/ship"; mk_git_ws "$WS6"; mk_backbone "$WS6"
HEAD6="$(git -C "$WS6/paper" rev-parse HEAD)"
WS="$WS6" SHA="$HEAD6" python3 - <<'PY'
import os, json
ws, sha = os.environ["WS"], os.environ["SHA"]
d = {"schema":"auto-research-milestone@1","milestones":{},"stages":{}}
for s in ("verify_final","spec_freeze"):
    d["stages"][s] = {"completed_at":"t","paper_commit":sha}
d["stages"]["verify_final"]["ambition_reconciled"] = True   # the owner-Ship ingest records this
json.dump(d, open(os.path.join(ws,"milestone-state.json"),"w"))
PY
out6="$(bash "$STATUS" "$WS6" --require verify_final,spec_freeze 2>/dev/null)"; rc6=$?
chk "#6 pipeline_status reconciled:true → SHIP_READY yes" "printf '%s\n' \"$out6\" | grep -q '^SHIP_READY yes\$'"
chk "#6 pipeline_status reconciled:true → exit 0"        "[ \"$rc6\" -eq 0 ]"

# ── #7 RESCUE fixture: after the rescue reopens ONE more round, loop_gate is BOUNDED — a clean round (accept) at
#      round=max+1 → EXIT (clean rescue ships); a still-unclean round (major_revision) → EXIT_AT_CAP (re-surfaces
#      the terminal gate for another owner decision — never an auto-loop). ─────────────────────────────────────
MAX="$(python3 -c "import yaml;print(yaml.safe_load(open('$CFG'))['max_loop_rounds'])")"
RN=$((MAX + 1))
gaterun(){ printf '%s' "$1" > "$TMP/gin.json"; bash "$GATE" "$TMP/gin.json" 2>&1 | head -1; }
v7a="$(gaterun "{\"round\":$RN,\"overall_risk\":\"accept\",\"new_handoff_items\":0,\"write_backs\":0}")"
chk "#7 rescue round=max+1 & accept → EXIT (clean rescue ships)" "[ \"$v7a\" = EXIT ]"
v7b="$(gaterun "{\"round\":$RN,\"overall_risk\":\"major_revision\",\"new_handoff_items\":0,\"write_backs\":0}")"
chk "#7 rescue round=max+1 & major_revision → EXIT_AT_CAP (re-gates, bounded)" "[ \"$v7b\" = EXIT_AT_CAP ]"

echo "----"; echo "t51_terminal_gate: $pass passed, $fail failed"; [ "$fail" = 0 ]
