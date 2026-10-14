#!/usr/bin/env bash
# T46 — bin/milestone_done.sh provenance hardening (RC-12): a recorded commit must RESOLVE in its repo, and
# with --require-segment-commits every EXPERIMENTS/<id>/result.md must cite a resolvable ws/code commit
# (the E3-ghost class: result.md claims PASS but the producer was never committed). Run: bash tests/t46_milestone_done_provenance.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MD="$ROOT/bin/milestone_done.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
WS="$TMP/ws"; mkdir -p "$WS/code" "$WS/EXPERIMENTS/E3"
MS="$WS/milestone-state.json"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

# A) no git repo + field present => legacy fallback DONE (backward compat for fixtures)
printf '{"milestones":{"M":{"completed_at":"t","code_commit":"deadbeef"}}}' > "$MS"
bash "$MD" "$WS" M; [ $? -eq 0 ] && ok "no-git fixture: field present => done (legacy fallback)" || no "legacy fallback broke"

# B) git repo + BOGUS recorded sha => NOT done
git -C "$WS/code" init -q; git -C "$WS/code" config user.email a@b.c; git -C "$WS/code" config user.name t
echo x > "$WS/code/f"; git -C "$WS/code" add -A; git -C "$WS/code" commit -qm init
bash "$MD" "$WS" M; [ $? -eq 1 ] && ok "git repo + bogus sha => NOT done (exit 1)" || no "bogus sha accepted as done"

# C) git repo + REAL sha => done
REAL=$(git -C "$WS/code" rev-parse HEAD)
python3 -c "import json,sys;p=sys.argv[1];d=json.load(open(p));d['milestones']['M']['code_commit']=sys.argv[2];json.dump(d,open(p,'w'))" "$MS" "$REAL"
bash "$MD" "$WS" M; [ $? -eq 0 ] && ok "git repo + resolvable sha => done" || no "resolvable sha not accepted"

# D) --require-segment-commits: E3/result.md with NO resolvable commit => NOT done
echo "Verdict: PASS. Reproduce: python code/equivariance_full_test.py" > "$WS/EXPERIMENTS/E3/result.md"
bash "$MD" "$WS" M --require-segment-commits; [ $? -eq 1 ] && ok "segment with uncommitted producer => NOT done (E3 ghost caught)" || no "E3 ghost passed"

# E) --require-segment-commits: E3/result.md WITH resolvable commit => done
echo "Verdict: PASS. Code commit: $REAL" > "$WS/EXPERIMENTS/E3/result.md"
bash "$MD" "$WS" M --require-segment-commits; [ $? -eq 0 ] && ok "segment with committed producer => done" || no "committed segment not accepted"

# F) without the flag, the segment is NOT checked (backward compat)
echo "Verdict: PASS (no commit cited)" > "$WS/EXPERIMENTS/E3/result.md"
bash "$MD" "$WS" M; [ $? -eq 0 ] && ok "no flag => segment commit NOT required (compat)" || no "segment gated without flag"

echo "----"; echo "t46_milestone_done_provenance: $pass passed, $fail failed"; [ "$fail" = 0 ]
