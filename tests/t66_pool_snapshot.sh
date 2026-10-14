#!/usr/bin/env bash
# t66 — bin/snapshot_ideation_pool.py. Proves: full-copy of small pool files, the trim rule (an oversized
# candidates[] JSON becomes an ids+titles .index.json, never a truncated copy), idempotence (second call
# is a no-op), expiry tolerance (missing sources -> action:"missing", exit 0), and exit 2 only when the
# week is underivable from the seed path.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }
SP="$ROOT/bin/snapshot_ideation_pool.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
D="$TMP/data-root"; WS="$TMP/ws"
W="2026-06-30"
SEED="data/ideations/$W/refined/2506.00001-idea1.md"

# --- build a synthetic pool ---
mkdir -p "$D/data/cache" "$D/data/ideations/$W/refined" "$WS"
python3 - "$D/data/cache/week-$W-candidates.json" <<'EOF'
import json, sys
doc = {"week": "w", "candidates": [{"arxiv_id": "2506.%05d" % i, "title": "T%d" % i,
        "abstract": "A" * 700} for i in range(2000)]}
json.dump(doc, open(sys.argv[1], "w"))
EOF
echo '{"top":[{"arxiv_id":"2506.00001","why_it_matters":"w"}],"rest":[]}' > "$D/data/cache/week-$W-rerank.json"
echo '{"2506.00001":{"result":{"ok":true,"why":""}}}' > "$D/data/cache/week-$W-judge-cache.json"
echo '{"papers":[]}' > "$D/data/cache/week-$W-gated-pool.json"
echo '{"ideas":[]}' > "$D/data/ideations/$W/2506.00001.json"
echo '{"rejected_candidates":[{"working_title":"x","why_rejected":"prior art"}]}' > "$D/data/ideations/$W/evidence-2506.00001.json"
echo '{"verdicts":[]}' > "$D/data/ideations/$W/.integrity.json"
echo "# refined seed" > "$D/data/ideations/$W/$(basename "$SEED")" 2>/dev/null || true
echo "# refined seed" > "$D/data/ideations/$W/refined/2506.00001-idea1.md"

# === Case 1: snapshot — copies, trims the oversized candidates, records missing canon files ===
OUT="$(python3 "$SP" --data-root "$D" --ws "$WS" --seed-file "$SEED" 2>&1)"; R=$?
M="$WS/ideation-pool-snapshot/snapshot-manifest.json"
if [ "$R" = "0" ] && [ -f "$M" ] && echo "$OUT" | grep -q "OK pool_snapshot: week=$W"; then
  ok "snapshot runs clean and writes manifest"; else no "snapshot run ($R: $OUT)"; fi

# === Case 2: trim rule — candidates became ids+titles .index.json, no full copy ===
IDX="$WS/ideation-pool-snapshot/cache/week-$W-candidates.index.json"
if [ -f "$IDX" ] && [ ! -f "$WS/ideation-pool-snapshot/cache/week-$W-candidates.json" ] \
   && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["count"]==2000; c=d["candidates"][0]; assert set(c)=={"arxiv_id","title"}' "$IDX" 2>/dev/null; then
  ok "trim rule: oversized candidates[] -> {arxiv_id,title} index, never truncated JSON"; else no "trim rule"; fi

# === Case 3: small files full-copied (judge-cache is the near-miss record; refined + evidence too) ===
if [ -f "$WS/ideation-pool-snapshot/cache/week-$W-judge-cache.json" ] \
   && [ -f "$WS/ideation-pool-snapshot/ideations/evidence-2506.00001.json" ] \
   && [ -f "$WS/ideation-pool-snapshot/ideations/.integrity.json" ] \
   && [ -f "$WS/ideation-pool-snapshot/ideations/refined/2506.00001-idea1.md" ]; then
  ok "small pool files full-copied (judge-cache / evidence / integrity / refined)"; else no "full copies"; fi

# === Case 4: manifest records missing canon files (prefetched/scout/quality-gate never existed) ===
if python3 -c '
import json,sys
m=json.load(open(sys.argv[1]))
acts={f["src"].split("/")[-1]:f["action"] for f in m["files"]}
assert acts.get("week-'$W'-prefetched.json")=="missing"
assert acts.get("week-'$W'-candidates.json")=="trimmed"
assert m["totals"]["missing"]>=3 and m["totals"]["trimmed"]==1
' "$M" 2>/dev/null; then
  ok "manifest actions: trimmed + missing canon files tallied"; else no "manifest actions"; fi

# === Case 5: idempotence — second call is a no-op ===
OUT2="$(python3 "$SP" --data-root "$D" --ws "$WS" --seed-file "$SEED" 2>&1)"; R2=$?
if [ "$R2" = "0" ] && echo "$OUT2" | grep -q "already taken"; then
  ok "idempotent: second call no-op"; else no "idempotence ($R2: $OUT2)"; fi

# === Case 6: expiry simulation — pool deleted, fresh ws still exits 0 with missing entries ===
rm -rf "$D/data/cache" "$D/data/ideations"; WS2="$TMP/ws2"; mkdir -p "$WS2"
OUT3="$(python3 "$SP" --data-root "$D" --ws "$WS2" --seed-file "$SEED" 2>&1)"; R3=$?
if [ "$R3" = "0" ] && echo "$OUT3" | grep -q "copied=0" \
   && python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); assert all(f["action"]=="missing" for f in m["files"])' \
        "$WS2/ideation-pool-snapshot/snapshot-manifest.json" 2>/dev/null; then
  ok "expiry-tolerant: all-missing pool still exits 0 with a manifest"; else no "expiry tolerance ($R3)"; fi

# === Case 7: underivable week -> exit 2 ===
python3 "$SP" --data-root "$D" --ws "$WS" --seed-file "some/odd/path.md" >/dev/null 2>&1; R4=$?
if [ "$R4" = "2" ]; then ok "underivable week -> exit 2 (the only hard failure)"; else no "week derivation ($R4)"; fi

echo "----"; echo "t66_pool_snapshot: $pass passed, $fail failed"; [ "$fail" = 0 ]
