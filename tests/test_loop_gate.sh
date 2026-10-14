#!/usr/bin/env bash
# Deterministic check of bin/loop_gate.sh (HANDOFF §5 B3 / PROTOCOL §4 "fed fixture JSON, output
# checked"). Generates round-input fixtures, runs the gate, asserts the verdict on line 1.
# Run from anywhere: bash tests/test_loop_gate.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$ROOT/bin/loop_gate.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0

check() { # name  json  expected_verdict  expected_exit
  local name="$1" json="$2" want="$3" wantrc="$4"
  printf '%s' "$json" > "$TMP/in.json"
  local out rc
  out="$(bash "$GATE" "$TMP/in.json" 2>&1)"; rc=$?
  local got; got="$(printf '%s\n' "$out" | head -1)"
  if [ "$got" = "$want" ] && [ "$rc" = "$wantrc" ]; then
    echo "PASS  $name -> $got (rc=$rc)"; pass=$((pass+1))
  else
    echo "FAIL  $name -> got '$got' rc=$rc, want '$want' rc=$wantrc"; echo "      $out"; fail=$((fail+1))
  fi
}

check "accept, no handoff, no writeback"        '{"round":1,"overall_risk":"accept","new_handoff_items":0,"write_backs":0}'         EXIT        0
check "minor_revision clean (round 2)"          '{"round":2,"overall_risk":"minor_revision","new_handoff_items":0,"write_backs":0}' EXIT        0
check "major_revision under cap -> continue"    '{"round":1,"overall_risk":"major_revision","new_handoff_items":0,"write_backs":0}' CONTINUE    0
check "clean risk but new handoff items (under cap)" '{"round":1,"overall_risk":"minor_revision","new_handoff_items":2,"write_backs":0}' CONTINUE    0
check "[unified-loop] write-backs no longer block EXIT (drafter rewrites every round)" '{"round":1,"overall_risk":"accept","new_handoff_items":0,"write_backs":3}' EXIT 0
check "major_revision AT/BEYOND cap (fixture round 5 >= live config max_loop_rounds; >= semantics) -> ship anyway" '{"round":5,"overall_risk":"major_revision","new_handoff_items":0,"write_backs":0}' EXIT_AT_CAP 0
check "reject at cap (round 6) -> ship anyway"  '{"round":6,"overall_risk":"reject","new_handoff_items":1,"write_backs":0}'          EXIT_AT_CAP 0
check "major_revision at cap (round 6) -> ship anyway" '{"round":6,"overall_risk":"major_revision","new_handoff_items":0,"write_backs":0}' EXIT_AT_CAP 0
check "malformed input (missing key)"           '{"round":1,"overall_risk":"accept"}'                                               "ERROR loop_gate: malformed round-input.json (need round/overall_risk/new_handoff_items/write_backs): 'new_handoff_items'" 2

# ── Soft floor (min_loop_rounds) — advisory only: never alters the verdict, only flags a below-floor
#    clean EXIT for FINAL-REPORT. Merges the t26_min_loop_floor coverage (Doc C §5.2 #7). ─────────────
check_substr() { # name  json  needle  want_present(1/0)
  local name="$1" json="$2" needle="$3" want="$4"
  printf '%s' "$json" > "$TMP/in.json"
  local out; out="$(bash "$GATE" "$TMP/in.json" 2>&1)"
  local has; if printf '%s' "$out" | grep -qF "$needle"; then has=1; else has=0; fi
  if [ "$has" = "$want" ]; then
    echo "PASS  $name"; pass=$((pass+1))
  else
    echo "FAIL  $name -> needle '$needle' present=$has, want=$want"; echo "      $out"; fail=$((fail+1))
  fi
}
# soft floor is now min_loop_rounds=1 (simplify 2026-06-19) — the floor is effectively inert: any clean exit
# is AT or ABOVE the floor, so it EXITs and is NOT flagged early. These assert the floor does not false-fire.
check        "clean exit above floor (round 4) still EXITs"      '{"round":4,"overall_risk":"accept","new_handoff_items":0,"write_backs":0}' EXIT 0
check_substr "clean exit above floor (round 4) is NOT flagged"   '{"round":4,"overall_risk":"accept","new_handoff_items":0,"write_backs":0}' "CONVERGED EARLY" 0
check_substr "above-floor status line carries below_floor=False" '{"round":4,"overall_risk":"accept","new_handoff_items":0,"write_backs":0}' "below_floor=False" 1
# clean exit AT the soft floor (round 5): EXIT with no early-convergence flag.
check        "at-floor clean exit (round 5) EXITs"               '{"round":5,"overall_risk":"accept","new_handoff_items":0,"write_backs":0}' EXIT 0
check_substr "at-floor clean exit (round 5) is NOT flagged"      '{"round":5,"overall_risk":"accept","new_handoff_items":0,"write_backs":0}' "CONVERGED EARLY" 0
# not-clean UNDER the cap still just CONTINUEs (floor never forces anything).
check        "not-clean under cap (round 1) -> continue"         '{"round":1,"overall_risk":"reject","new_handoff_items":0,"write_backs":0}' CONTINUE 0

echo "----"
echo "loop_gate: $pass passed, $fail failed"
[ "$fail" = 0 ]
