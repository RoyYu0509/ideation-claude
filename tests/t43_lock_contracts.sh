#!/usr/bin/env bash
# T43 — bin/lock_contracts.sh + bin/contract_lock_status.sh: the DETERMINISTIC Phase-0(C) lock that the LLM
# used to skip (so the locks never existed and V5 silently "legacy-passed" a WEAKEN). Run: bash tests/t43_lock_contracts.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK="$ROOT/bin/lock_contracts.sh"; STAT="$ROOT/bin/contract_lock_status.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
WS="$TMP/runs/p"; mkdir -p "$WS"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

# A HANDOFF with both machine-readable blocks under their canonical headers.
cat > "$WS/HANDOFF.md" <<'EOF'
# HANDOFF
## §4b SCALE-CONTRACT (machine-readable — the DEPTH contract)
```yaml
scale_contract:
  version: 1
  criteria:
    K1: { holds_across: "every cell", anchors: [{ metric: "raw F-RMSCE", success: "<= x" }], evidence: { type: direct, claimed: "F-RMSCE on the claimed class", measured: "raw F-RMSCE on that class", gap: null } }
```
## §4c AMBITION CONTRACT (machine-readable — the BREADTH contract)
```yaml
ambition_contract:
  version: 1
  central_result: { claim: "the headline" }
```
EOF

# 1) ABSENT before locking
[ "$(bash "$STAT" "$WS" 2>/dev/null; echo)" ]; bash "$STAT" "$WS" >/dev/null 2>&1; [ $? -eq 1 ] \
  && ok "status ABSENT (exit 1) before lock" || no "status not ABSENT before lock"

# 2) first lock writes BOTH .locked.json
bash "$LOCK" "$WS" >/dev/null 2>&1 && [ -f "$WS/HANDOFF.scale-contract.locked.json" ] \
  && [ -f "$WS/HANDOFF.ambition.locked.json" ] && ok "first lock wrote both .locked.json" \
  || no "first lock did not write both locks"

# 3) the lock captured the §4b yaml content + a sha — verbatim, including the per-K evidence declaration
python3 - "$WS/HANDOFF.scale-contract.locked.json" <<'PY' && ok "scale lock has content+sha256 (incl. evidence type)" || no "scale lock missing content/sha/evidence"
import json,sys; d=json.load(open(sys.argv[1]))
assert d.get("sha256") and "scale_contract:" in (d.get("content") or ""), d
assert "type: direct" in d["content"], "per-K evidence block not captured verbatim in the lock"
PY

# 4) status LOCKED now
bash "$STAT" "$WS" >/dev/null 2>&1 && ok "status LOCKED (exit 0) after lock" || no "status not LOCKED after lock"

# 5) re-lock WITHOUT --ratchet refuses (exit 2)
bash "$LOCK" "$WS" >/dev/null 2>&1; [ $? -eq 2 ] && ok "re-lock without --ratchet refused (exit 2)" \
  || no "re-lock without --ratchet was allowed (silent overwrite of the immutable baseline)"

# 6) --ratchet re-lock records prev_sha256
bash "$LOCK" "$WS" --ratchet >/dev/null 2>&1 \
  && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['ratchet'] and d['prev_sha256']" "$WS/HANDOFF.scale-contract.locked.json" 2>/dev/null \
  && ok "--ratchet re-lock records prev_sha256" || no "--ratchet re-lock did not record prev_sha256"

# 7) a HANDOFF MISSING the §4c block => exit 2, and NO half-lock left behind
WS2="$TMP/runs/q"; mkdir -p "$WS2"
printf '# H\n## §4b SCALE-CONTRACT\n```yaml\nscale_contract: {version: 1}\n```\n' > "$WS2/HANDOFF.md"
bash "$LOCK" "$WS2" >/dev/null 2>&1; rc=$?
[ $rc -eq 2 ] && [ ! -f "$WS2/HANDOFF.scale-contract.locked.json" ] \
  && ok "missing §4c block => exit 2, no half-lock written" || no "missing §4c block not handled (rc=$rc / half-lock left)"

echo "----"; echo "t43_lock_contracts: $pass passed, $fail failed"; [ "$fail" = 0 ]
