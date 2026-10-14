#!/usr/bin/env bash
# bin/loop_gate.sh — deterministic LOOP exit arithmetic for the auto-research Stage B loop
# (HANDOFF §5 B3). Real code, not judgement. The L0 spec runs this once per round and branches on
# the FIRST stdout line:
#   EXIT        — clean: ship the rigorous, reviewer-hardened draft.
#   CONTINUE    — not clean and under the cap: run another experiment+draft round.
#   EXIT_AT_CAP — not clean but at max_loop_rounds: L0 SURFACES the unified terminal gate (Abandon
#                 [default] / Ship / Rescue one more round); NEVER a silent auto-ship at the cap.
#                 FINAL-REPORT(-killed).md lists every unresolved reject/major item.
#
# Usage:  bin/loop_gate.sh <round-input.json>
#   <round-input.json> = { "round": <int>=1.., "overall_risk": "reject|major_revision|
#     minor_revision|accept", "new_handoff_items": <int>, "write_backs": <int> }
#   L0 assembles this each round from the review L1's return envelope (overall_risk = the paper
#   -polish AC_SCHEMA.overall_risk; new_handoff_items = new_exhibit experiments exported to the round
#   HANDOFF; write_backs is carried for logging only — NOT used in the gate arithmetic).
#
# Thresholds come from config/config.yaml (max_loop_rounds + loop_gate.exit_risk) — SSOT, no
# hardcoded copy. FAIL-LOUD: a missing config key or malformed input prints "ERROR ..." and exits 2.
set -euo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONFIG_PATH="${ROOT}/config/config.yaml"
INPUT="${1:-}"

[ -n "$INPUT" ]       || { echo "ERROR loop_gate: need <round-input.json> argument"; exit 2; }
[ -f "$INPUT" ]       || { echo "ERROR loop_gate: input file not found: $INPUT"; exit 2; }
[ -f "$CONFIG_PATH" ] || { echo "ERROR loop_gate: config not found: $CONFIG_PATH"; exit 2; }

CONFIG_PATH="$CONFIG_PATH" INPUT="$INPUT" python3 - <<'PY'
import os, sys, json, yaml

def fail(msg):
    print("ERROR loop_gate: " + msg); sys.exit(2)

try:
    cfg = yaml.safe_load(open(os.environ["CONFIG_PATH"]))
except Exception as e:
    fail("cannot parse config.yaml (%s)" % e)

def need(d, *path):
    node = d
    for seg in path:
        if not isinstance(node, dict) or seg not in node:
            fail("<MISSING KEY: %s>" % ".".join(path))
        node = node[seg]
    return node

max_rounds = need(cfg, "max_loop_rounds")
min_rounds = need(cfg, "min_loop_rounds")                    # SOFT floor (advisory) — Doc A §6.3 / Doc C §2.2
exit_risk  = need(cfg, "loop_gate", "exit_risk")
valid_risk = need(cfg, "loop_gate", "valid_risk")            # full AC enum (SSOT) — input MUST be one of these
if not isinstance(max_rounds, int) or max_rounds < 1:
    fail("max_loop_rounds must be an int >= 1, got %r" % (max_rounds,))
# Soft floor is advisory: it NEVER forces CONTINUE (clean early-exit stays allowed) and NEVER changes the
# verdict — it only annotates a below-floor clean EXIT for FINAL-REPORT. But it must be a sane int in [1, max].
if not isinstance(min_rounds, int) or not (1 <= min_rounds <= max_rounds):
    fail("min_loop_rounds must be an int in [1, max_loop_rounds=%r], got %r" % (max_rounds, min_rounds))
if not isinstance(exit_risk, list) or not exit_risk:
    fail("loop_gate.exit_risk must be a non-empty list, got %r" % (exit_risk,))
if not isinstance(valid_risk, list) or not valid_risk:
    fail("loop_gate.valid_risk must be a non-empty list, got %r" % (valid_risk,))
# normalize both lists for case/space-insensitive membership (B.6: "ACCEPT"/"accept " must not burn a round)
valid_risk = [str(x).strip().lower() for x in valid_risk]
exit_risk  = [str(x).strip().lower() for x in exit_risk]
bad = [r for r in exit_risk if r not in valid_risk]
if bad:
    fail("loop_gate.exit_risk %r not a subset of valid_risk %r" % (bad, valid_risk))

try:
    inp  = json.load(open(os.environ["INPUT"]))
    rnd  = int(inp["round"])
    risk = str(inp["overall_risk"]).strip().lower()          # normalize (B.6): trailing space / case never burns a round
    nh   = int(inp["new_handoff_items"])
    wb   = int(inp["write_backs"])
except Exception as e:
    fail("malformed round-input.json (need round/overall_risk/new_handoff_items/write_backs): %s" % e)
if rnd < 1:
    fail("round must be >= 1, got %d" % rnd)
# FAIL LOUD on an out-of-enum verdict — never fall through to a silent EXIT_AT_CAP ship at the cap (RC-3/RC-4, B.6 #1).
if risk not in valid_risk:
    fail("overall_risk %r not in AC enum valid_risk=%r — refusing to gate (fail loud, not fail open)" % (risk, valid_risk))

clean  = (risk in exit_risk) and (nh == 0)   # [unified-loop] wb dropped: the DRAFT stage rewrites the whole paper every round, so write_backs is not a convergence signal (verify-PASS is enforced by the L0 RC-1 belt)
at_cap = rnd >= max_rounds
verdict = "EXIT" if clean else ("EXIT_AT_CAP" if at_cap else "CONTINUE")

below_floor = clean and (rnd < min_rounds)                  # advisory flag only — does NOT alter the verdict

print(verdict)
print("round=%d/%d (soft floor %d) overall_risk=%s exit_risk=[%s] new_handoff_items=%d write_backs=%d clean=%s at_cap=%s below_floor=%s"
      % (rnd, max_rounds, min_rounds, risk, ",".join(map(str, exit_risk)), nh, wb, clean, at_cap, below_floor))
if verdict == "EXIT":
    if below_floor:
        print("reason: AC verdict acceptable AND 0 new handoff items — clean EXIT, but "
              "CONVERGED EARLY at round %d (< soft floor %d): FINAL-REPORT.md must note the early convergence."
              % (rnd, min_rounds))
    else:
        print("reason: AC verdict is acceptable AND 0 new handoff items this round (+ focused verify PASS, enforced by L0) — ship.")
elif verdict == "CONTINUE":
    bits = []
    if risk not in exit_risk: bits.append("overall_risk=%s not in exit set" % risk)
    if nh: bits.append("%d new handoff item(s) feed the next experiment round" % nh)
    print("reason: " + "; ".join(bits) + " — run another round.")
else:
    print("reason: at max_loop_rounds without a clean exit — L0 SURFACES the unified terminal gate "
          "(Abandon [default] / Ship / Rescue one more round); NEVER a silent auto-ship at the cap. "
          "FINAL-REPORT(-killed).md must list every unresolved reject/major item prominently.")
PY
