#!/usr/bin/env bash
# auto-research — deterministic SHIP-GATE (PreToolUse hook).
#
# WHY THIS EXISTS (RC-11). spec/research.js is a constitution an L0 agent REPRODUCES with harness tools, not
# executed JS. RC-10 added a disk-derived ship-gate (assertShipReady -> bin/pipeline_status.sh) but it lives
# INSIDE ship(); STATUS-MODEL.md §8 spelled out the residual hole: "if L0 skips the whole finishing block it
# also skips recordStage + ship(), so the gate never runs — the only fully L0-proof enforcement is a harness
# hook." The 2026-06-21 real run hit exactly that: at EXIT_AT_CAP L0 judged "the science is broken, finishing
# is pointless", skipped verify_final -> rewrite -> polish_figures -> cross_check AND ship(), and improvised a
# FINAL-REPORT.md to declare the paper shipped. The in-spec gate never fired because L0 never reached it.
#
# This hook closes §8's last mile: it moves the SAME oracle (bin/pipeline_status.sh) OUTSIDE the reproduction,
# where the harness enforces it and L0 cannot reason past it. The real logic is in the sibling Python file
# (robust JSON + oracle invocation); this wrapper just forwards the hook's stdin payload to it.
exec python3 "${BASH_SOURCE%/*}/ship_gate.py"
