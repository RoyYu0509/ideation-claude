#!/usr/bin/env bash
# T47 — RC-12 enactment wiring (static): the previously LLM-reproduced [[MECH]] steps are now code-enforced —
# research.js CALLS the deterministic bin/ scripts at the right transitions, the inline round-freeze the L0
# could skip is GONE, now() is a real timestamp, and VERIFY-PROTOCOL grew the V5 fail-closed + V8 metric
# conformance guards. A regression net so the determinism can't silently slip back to prose. Run: bash tests/t47_enactment_wiring.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RJS="$ROOT/spec/research.js"; VP="$ROOT/spec/spawn-prompts/VERIFY-PROTOCOL.md"; HJ="$ROOT/hooks/hooks.json"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }
has(){ grep -qF -- "$2" "$1"; }

# research.js wires each new deterministic script
has "$RJS" "bin/archive_decision.sh"     && ok "research.js calls archive_decision.sh"     || no "archive_decision.sh not wired"
has "$RJS" "bin/lock_contracts.sh"       && ok "research.js calls lock_contracts.sh"       || no "lock_contracts.sh not wired"
has "$RJS" "bin/contract_lock_status.sh" && ok "research.js calls contract_lock_status.sh" || no "contract_lock_status.sh not wired"
has "$RJS" "bin/round_setup.sh"          && ok "research.js calls round_setup.sh"          || no "round_setup.sh not wired"
has "$RJS" "--require-segment-commits"   && ok "research.js documents the segment-commit gate" || no "segment-commit gate not noted"

# the inline round-freeze the L0 skipped is GONE (replaced by the bin/ call)
grep -q 'writeJson(`${ws}/.round-${state.loop_round}.concerns.json`' "$RJS" \
  && no "inline round concern writeJson still present (should be bin/round_setup.sh)" \
  || ok "inline round-freeze removed (now bin/round_setup.sh)"

# now() is enacted as a real UTC timestamp, not a constant
has "$RJS" 'now(): [[MECH]] enact as `bash(date -u' && ok "now() defined as a real shell timestamp" || no "now() still undefined/constant"

# VERIFY-PROTOCOL grew V5 fail-closed + single-source + V8 metric conformance
has "$VP" "FAIL-CLOSED: if that lock file is ABSENT" && ok "V5 fail-closed on absent lock" || no "V5 fail-closed missing"
has "$VP" "LOCK, not the prose, is the binding criteria source" \
  && ok "V5 single-source-of-truth clause" || no "V5 single-source clause missing"
has "$VP" "METRIC CONFORMANCE" && ok "V8 metric-conformance clause" || no "V8 metric-conformance missing"
has "$VP" "frmsce_recal" && ok "V8 names the frmsce_recal reward-hack" || no "V8 recal example missing"

# decision_guard registered
has "$HJ" "decision_guard.sh" && ok "decision_guard.sh registered in hooks.json" || no "decision_guard not registered"

echo "----"; echo "t47_enactment_wiring: $pass passed, $fail failed"; [ "$fail" = 0 ]
