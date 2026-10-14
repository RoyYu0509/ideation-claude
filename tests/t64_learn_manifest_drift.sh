#!/usr/bin/env bash
# t64 — /learn manifest DRIFT SELF-TEST (P-6 fix, dossier 02, 2026-07-07): bin/learn_manifest.py's artifact-
# family globs are HAND-MAINTAINED and drifted from the real filenames a live run actually produces (c1-wave-
# ledgers, c1-detach-logs, a-candidate-pool's gated-pool glob all under-reported to ZERO on a real run before
# anyone noticed). Unlike t60 (which deliberately covers OLD-vintage names), this fixture uses TODAY's real,
# CURRENT-vintage filenames so any FUTURE drift away from what a live run actually writes fails LOUD here
# instead of silently under-reporting in a real /learn retro. Standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }
LM="$ROOT/bin/learn_manifest.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

D="$TMP/root"; WS="$D/runs/demo"
mkdir -p "$D/state" "$WS/EXPERIMENTS/E1/logs" "$WS/EXPERIMENTS/phase0/logs" "$D/data/cache"
printf '%s\n' '{"stage":"loop","paper_slug":"demo","loop_round":1}' > "$D/state/pipeline-state.json"
: > "$D/state/run-events.jsonl"
echo '{}' > "$WS/milestone-state.json"
# CURRENT-vintage wave-ledger filename: hyphenated, ONE per wave dir — NOT the old "wave1.ledger.json" shape.
echo '{"runs":[]}' > "$WS/EXPERIMENTS/E1/wave-ledger.json"
echo '{"runs":[]}' > "$WS/EXPERIMENTS/phase0/wave-ledger.json"
# CURRENT-vintage detach logs: under EXPERIMENTS/<wave>/logs/, NOT .polish/logs/.
echo "log"  > "$WS/EXPERIMENTS/E1/logs/e1.stdout.log"
echo "0"    > "$WS/EXPERIMENTS/E1/logs/e1.exitcode"
# CURRENT-vintage gated-pool cache filename: week-<W>-gated-pool.json, NOT gated-pool*.json.
echo '{}' > "$D/data/cache/week-2026-W27-gated-pool.json"
# quality-ceiling upgrade (2026-07-07): full pool + prefetch scores + judge near-misses are D4 evidence.
echo '{"candidates":[]}' > "$D/data/cache/week-2026-W27-candidates.json"
echo '{}' > "$D/data/cache/week-2026-W27-prefetched.json"
echo '{}' > "$D/data/cache/week-2026-W27-judge-cache.json"
# pool snapshot taken at pick time (bin/snapshot_ideation_pool.py) — ws-scoped, survives cache cleanup.
mkdir -p "$WS/ideation-pool-snapshot/cache" "$WS/ideation-pool-snapshot/ideations/refined"
echo '{"schema":"auto-research-pool-snapshot@1"}' > "$WS/ideation-pool-snapshot/snapshot-manifest.json"
echo '{}' > "$WS/ideation-pool-snapshot/cache/week-2026-W27-judge-cache.json"
echo "# seed" > "$WS/ideation-pool-snapshot/ideations/refined/2506.00001-idea1.md"
# amplify + rescue verdicts persisted per round (both outcomes / all scenarios).
echo '{"schema":"auto-research-amplify-verdict@1","outcome":"at_ceiling"}' > "$WS/.round-1.amplify-verdict.json"
echo '[{"schema":"auto-research-rescue-verdict@1","verdict":"not_retained"}]' > "$WS/.round-1.rescue-verdicts.json"

OUT="$(python3 "$LM" --data-root "$D" --run-id R1 --slug demo --ws "$WS")" || { no "manifest run exits 0"; echo "$OUT"; }
LDIR="$D/state/learning/R1"

# === Case 1: current-vintage wave-ledger.json (2 waves) is found, not silently 0 ===
if python3 -c "
import json
m=json.load(open('$LDIR/manifest.json'))
fams={a['family']:a for g in m['groups'].values() for a in g['artifacts']}
assert fams['c1-wave-ledgers']['count']==2, fams['c1-wave-ledgers']
" 2>/dev/null; then ok "c1-wave-ledgers finds current-vintage wave-ledger.json (2)"; else no "c1-wave-ledgers drifted"; fi

# === Case 2: current-vintage EXPERIMENTS/*/logs/* is found ===
if python3 -c "
import json
m=json.load(open('$LDIR/manifest.json'))
fams={a['family']:a for g in m['groups'].values() for a in g['artifacts']}
assert fams['c1-detach-logs']['count']==2, fams['c1-detach-logs']
" 2>/dev/null; then ok "c1-detach-logs finds current-vintage EXPERIMENTS/*/logs/* (2)"; else no "c1-detach-logs drifted"; fi

# === Case 3: a-candidate-pool finds gated-pool + candidates + prefetched + judge-cache (4) ===
if python3 -c "
import json
m=json.load(open('$LDIR/manifest.json'))
fams={a['family']:a for g in m['groups'].values() for a in g['artifacts']}
assert fams['a-candidate-pool']['count']==4, fams['a-candidate-pool']
" 2>/dev/null; then ok "a-candidate-pool finds pool+candidates+prefetched+judge-cache (4)"; else no "a-candidate-pool drifted"; fi

# === Case 4: the pick-time pool snapshot family is indexed (manifest + cache file + refined dir + refined md = 4;
# the */* glob also counts the refined/ dir entry — informational, harmless) ===
if python3 -c "
import json
m=json.load(open('$LDIR/manifest.json'))
fams={a['family']:a for g in m['groups'].values() for a in g['artifacts']}
assert fams['a-pool-snapshot']['count']==4, fams['a-pool-snapshot']
" 2>/dev/null; then ok "a-pool-snapshot indexes the pick-time snapshot tree (4)"; else no "a-pool-snapshot missing"; fi

# === Case 5: amplify + rescue verdict files are indexed (c2-amplify family; rescue via c2-viability) ===
if python3 -c "
import json
m=json.load(open('$LDIR/manifest.json'))
fams={a['family']:a for g in m['groups'].values() for a in g['artifacts']}
assert fams['c2-amplify']['count']==1, fams['c2-amplify']
assert fams['c2-viability']['count']==1, fams['c2-viability']
" 2>/dev/null; then ok "c2-amplify + rescue-verdicts indexed (the [OPPORTUNITY] evidence)"; else no "amplify/rescue verdicts not indexed"; fi

echo "----"; echo "t64_learn_manifest_drift: $pass passed, $fail failed"; [ "$fail" = 0 ]
