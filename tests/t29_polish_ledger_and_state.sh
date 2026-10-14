#!/usr/bin/env bash
# T29 — refinement D (Doc A §10-E, DECISIONS D15): the /polish convergence model is now a CATEGORICAL
# state ladder (numeric weighting REMOVED), and /polish writes a DETERMINISTIC per-SECTION open-items
# ledger TASK_STATUS.polish.concerns.json (task-ledger id/concern/status schema). This test proves all of
# it MECHANICALLY/offline:
#   (1) scripts/polish_converge.py: the rewritten categorical decider PASSES its unit test (this is also
#       the first time the python test is wired into the suite — it ran nowhere before), and the file
#       carries the ladder (RANK / round_state) and NO weighted arithmetic.
#   (2) spec/polish.js: the D-1 ledger writer (recordSectionLedger + writePolishLedger) emits
#       TASK_STATUS.polish.concerns.json on the id/concern/status schema with a derived open_concerns set;
#       the D-2 reviewer rule (a cosmetic flag earns ≥1 attempt before it may be deferred) is present; the
#       de-scoring is REAL (no WEIGHTS / near_converged / all_pass / best_weighted left); it still parses.
#   (3) config: the flag_weights block is GONE; max_rounds / no_improvement_rounds remain.
#   (4) spec/research.js: polishGoal reads the spec-written ledger (pdPointer specWritten path), not by-hand.
# Run: bash tests/t29_polish_ledger_and_state.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VDIR="$ROOT/plugins/paper-polish-ar"
POL="$VDIR/spec/polish.js"
CONV="$VDIR/scripts/polish_converge.py"
TST="$VDIR/scripts/test_polish_converge.py"
VCFG="$VDIR/config/config.yaml"
SPEC="$ROOT/spec/research.js"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── (1) polish_converge.py — the categorical decider ──────────────────────────
chk "converge: unit test PASSES (now wired into the suite)"   "python3 '$TST'"
chk "converge: categorical RANK ladder present"               "grep -qF 'RANK = {' '$CONV'"
chk "converge: round_state collapses to one adjective"        "grep -qF 'def round_state(' '$CONV'"
chk "converge: empty-set convergence (state == clean)"        "grep -qF \"state == \\\"clean\\\"\" '$CONV'"
chk "converge: NO weighted arithmetic left"                   "! grep -qE 'compute_weighted|def near_converged|\"weights\"' '$CONV'"

# ── (2) spec/polish.js — D-1 ledger writer + D-2 rule + de-scoring ────────────
chk "polish: recordSectionLedger defined"                     "grep -qF 'function recordSectionLedger(' '$POL'"
chk "polish: writePolishLedger defined"                       "grep -qF 'function writePolishLedger(' '$POL'"
chk "polish: emits TASK_STATUS.polish.concerns.json"          "grep -qF 'TASK_STATUS.polish.concerns.json' '$POL'"
chk "polish: ledger item carries id/concern/status"           "grep -qF \"status: deferred ? 'deferred' : 'open'\" '$POL'"
chk "polish: open_concerns derived from open/reopened items"  "grep -qF 'open_concerns:' '$POL'"
chk "polish: concernFor maps flags to prose.* concerns"       "grep -qF 'function concernFor(' '$POL'"
chk "polish: cross-section sweep -> master_advisory bucket"   "grep -qF 'master_advisory' '$POL'"
chk "polish: D-2 reviewer rule (cosmetic earns one attempt)"  "grep -qF 'earns its one attempt' '$POL'"
# [dossier-12 G1] the serial inline loop was pointerized into spec/section-loop.md — the STATE-history +
# best-round-ladder invariants now live there (the callers only bind); assert the canonical file + the
# helpers that carry the exact payload shape.
chk "canonical loop: converge heredoc feeds a STATE history"  "grep -qF '\"history\":[{\"state\":' '$ROOT/plugins/paper-polish-ar/spec/section-loop.md' && grep -qF 'history: input.history' '$POL'"
chk "canonical loop: best-round laddered by state (best mode)" "grep -qF '{\"mode\":\"best\"' '$ROOT/plugins/paper-polish-ar/spec/section-loop.md' && grep -qF 'function pickBestRound' '$POL'"
chk "serial path reads the canonical loop (no inline copy)"   "grep -qF 'read \${pluginRoot}/spec/section-loop.md' '$POL'"
chk "polish: de-scoring REAL — no WEIGHTS/near/all_pass left" "! grep -qE 'const WEIGHTS|near_converged|all_pass|best_weighted' '$POL'"
chk "polish: parses (node --check)"                           "node --check '$POL'"

# ── (3) config — flag_weights removed, round knobs kept ──────────────────────
chk "config: flag_weights block REMOVED"                      "! grep -qE '^[[:space:]]*flag_weights:' '$VCFG'"
chk "config: max_rounds + no_improvement_rounds remain" \
    "python3 -c \"import yaml; c=yaml.safe_load(open('$VCFG'))['polish']; assert c['max_rounds'] and c['no_improvement_rounds']; assert 'flag_weights' not in c\""

# ── (4) spec/research.js — polishGoal reads the spec-written ledger ───────────
chk "research: pdPointer has a specWritten path"              "grep -qF 'specWritten' '$SPEC'"

echo "----"; echo "t29_polish_ledger_and_state: $pass passed, $fail failed"; [ "$fail" = 0 ]
