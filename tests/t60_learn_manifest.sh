#!/usr/bin/env bash
# t60 — bin/learn_manifest.py over a SYNTHETIC data root with BOTH artifact-name vintages + a fake
# cache/source pair. Proves: glob-family matching finds old AND new names, expected-but-absent families
# become gaps (evidence for the retro), per-group event slices are cut, the cache-vs-source snapshot
# detects spot drift, degraded traceless runs are flagged honestly, and the summary respects its 60-line
# cap. Standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }
LM="$ROOT/bin/learn_manifest.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# --- fake SOURCE repo + fake CACHE (auto-research materialized w/ DIFFERENT research.js -> drift) ---
SRC="$TMP/src"; CACHE="$TMP/cache"
mkdir -p "$SRC/spec" "$SRC/plugins/paper-polish-ar/spec" "$CACHE/auto-research/0.1.0/spec"
echo "source version AAA" > "$SRC/spec/research.js"
echo "review protocol"    > "$SRC/plugins/paper-polish-ar/spec/review-protocol.md"
echo "cache version BBB"  > "$CACHE/auto-research/0.1.0/spec/research.js"

# --- MODERN data root: done run, events, but REVIEW history + verify report MISSING (gap bait) ---
D="$TMP/root"; WS="$D/runs/demo"
mkdir -p "$D/state/decisions" "$WS/EXPERIMENTS/E1" "$WS/paper/sections" "$WS/.polish/logs" "$D/runs/_trace/R1"
printf '%s\n' '{"stage":"done","paper_slug":"demo","loop_round":2,"final_status":"shipped","venue":"V"}' > "$D/state/pipeline-state.json"
{
 printf '%s\n' '{"ts":"t1","run_id":"R1","event":"run_start","paper":null,"stage":"ideation"}'
 printf '%s\n' '{"ts":"t2","run_id":"R1","event":"gate_open","id":"GATE1","stage":"seed_gate"}'
 printf '%s\n' '{"ts":"t3","run_id":"R1","event":"round_setup","paper":"demo","stage":"loop"}'
 printf '%s\n' '{"ts":"t4","run_id":"R1","event":"verdict","paper":"demo","stage":"loop"}'
 printf '%s\n' '{"ts":"t5","run_id":"R1","event":"stage_recorded","paper":"demo","stage":"rewrite"}'
 printf '%s\n' '{"ts":"t6","run_id":"R1","event":"agent_spawn","paper":"demo","stage":"zzz_unknown_stage"}'
} > "$D/state/run-events.jsonl"
printf '%s\n' '{"session_id":"S1","run_id":"R1"}' > "$D/state/sessions.jsonl"
printf '%s\n' '# resolved' > "$D/state/decisions/DECISIONS-RESOLVED-1.md"
echo h > "$WS/HANDOFF.md"; echo p > "$WS/RESEARCH-PROTOCOL.md"; echo c > "$WS/.config-frozen.yaml"
echo '{}' > "$WS/HANDOFF.scale-contract.locked.json"; echo '{}' > "$WS/HANDOFF.ambition.locked.json"
echo '{"frozen":{"spec_commit":"abc1234"}}' > "$WS/milestone-state.json"
echo '{}' > "$WS/loop-gate-input-r1.json"; echo '{}' > "$WS/loop-gate-input-r2.json"
echo r > "$WS/EXPERIMENTS/E1/result.md"; echo '{"runs":[]}' > "$WS/EXPERIMENTS/wave1.ledger.json"
echo '{}' > "$WS/AUDIT-ARTIFACTS.locked.json"; echo '{}' > "$WS/AUDITED-VALUES.json"
echo l > "$WS/RESEARCH_LOG.md"; echo d > "$WS/DECISIONS.md"; echo f > "$WS/FAILURES.md"
echo dt > "$WS/differentiation_table.md"; echo b > "$WS/paper/references.bib"
echo s > "$WS/paper/sections/intro.tex"; echo m > "$WS/paper/master.tex"
echo rr > "$WS/paper/review-report.md"; echo fr > "$WS/FINAL-REPORT.md"
echo rw > "$WS/paper/rewrite-report.md"; echo pf > "$WS/paper/polish-figures-report.md"
echo cc > "$WS/paper/cross-check-report.md"
touch "$WS/.round-1.start" "$WS/.round-1.drafted"; echo '{}' > "$WS/.round-1.concerns.json"

OUT="$(python3 "$LM" --data-root "$D" --run-id R1 --slug demo --ws "$WS" --source-repo "$SRC" --cache-root "$CACHE")" || { no "manifest run exits 0"; echo "$OUT"; }
LDIR="$D/state/learning/R1"

# === Case 1: manifest written, parses, right identity ===
if python3 -c "
import json,sys
m=json.load(open('$LDIR/manifest.json'))
assert m['run_id']=='R1' and m['slug']=='demo' and m['completed'] is True
assert m['schema']=='auto-research-learn-manifest@1'
" 2>/dev/null; then ok "manifest.json written + identity/completed correct"; else no "manifest identity"; fi

# === Case 2: gaps flag EXPECTED-but-absent families (REVIEW history + verify report), not conditional ones ===
if python3 -c "
import json
m=json.load(open('$LDIR/manifest.json'))
fams={g['family'] for g in m['gaps']}
assert 'c2-review-history' in fams and 'c2-verify' in fams, fams
assert 'e-wechat' not in fams and 'd-fig-briefs' not in fams, fams
" 2>/dev/null; then ok "gaps: expected-absent flagged; conditional-absent NOT flagged"; else no "gaps semantics"; fi

# === Case 3: event slices cut per group; C1/C2 share the loop slice; unknown stage -> meta ===
if python3 -c "
import json
m=json.load(open('$LDIR/manifest.json'))
g=m['groups']
assert g['A']['event_count']==1 and g['B']['event_count']==1
assert g['C1']['event_count']==2 and g['C2']['event_count']==2
assert g['C1']['event_slice']==g['C2']['event_slice']
assert g['D']['event_count']==1 and g['F']['event_count']==1
" 2>/dev/null && [ "$(wc -l < "$LDIR/events-C.jsonl" | tr -d ' ')" = "2" ]; then
  ok "event slices per group (C shared, unknown stage -> meta)"; else no "event slices"; fi

# === Case 4: code worlds — auto-research cache DRIFTED; paper-polish-ar loaded from source ===
if python3 -c "
import json
m=json.load(open('$LDIR/manifest.json'))
w=m['code_worlds']
assert w['plugins']['auto-research']['loaded_from']=='cache'
assert w['plugins']['auto-research']['drift'] is True
assert w['plugins']['paper-polish-ar']['loaded_from']=='source'
assert w['run_spec_commit']=='abc1234'
" 2>/dev/null && echo "$OUT" | grep -q "drifted=auto-research"; then
  ok "code worlds: cache drift detected + run_spec_commit from frozen block"; else no "code worlds"; fi

# === Case 5: summary <=60 lines and carries the drift warning ===
LC="$(wc -l < "$LDIR/manifest-summary.md")"
if [ "$LC" -le 60 ] && grep -q "cache≠source" "$LDIR/manifest-summary.md"; then
  ok "summary <=60 lines ($LC) + drift warning"; else no "summary cap/drift ($LC)"; fi

# === Case 6: OLD-vintage traceless root — old names matched by the same families; degraded honest ===
D2="$TMP/old"; W2="$D2/runs/legacy"
mkdir -p "$W2/paper" "$D2/state"
printf '%s\n' '{"stage":"done","paper_slug":"legacy"}' > "$D2/state/pipeline-state.json"
echo h > "$W2/HANDOFF.md"; echo m > "$W2/paper/master.tex"
echo '{}' > "$W2/milestone-state.json"
echo '{}' > "$W2/loop_gate_input_r1.json"          # OLD underscore name
echo v > "$W2/VERIFY_FINAL_REPORT.md"              # OLD verify name
echo rv > "$W2/REVIEW_ROUND_1.md"                  # OLD review-history name
echo fr > "$W2/FINAL-REPORT.md"
OUT2="$(python3 "$LM" --data-root "$D2" --ws "$W2" --slug legacy --source-repo "$SRC" --cache-root "$CACHE")"
L2="$D2/state/learning/untraced-legacy"
if python3 -c "
import json
m=json.load(open('$L2/manifest.json'))
assert m['degraded']['events'] and m['degraded']['trace']
fams={a['family']:a for g in m['groups'].values() for a in g['artifacts']}
assert fams['c2-gate-inputs']['count']==1 and fams['c2-verify']['count']==1 and fams['c2-review-history']['count']==1
gapfams={g['family'] for g in m['gaps']}
assert 'c2-verify' not in gapfams and 'c2-review-history' not in gapfams
" 2>/dev/null; then ok "old vintage: underscore/legacy names matched; degraded flags honest"; else no "old vintage matching"; fi

echo "----"; echo "t60_learn_manifest: $pass passed, $fail failed"; [ "$fail" = 0 ]
