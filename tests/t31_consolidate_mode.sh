#!/usr/bin/env bash
# T31 — the fidelity hook's "consolidate" mode (REWRITE-CONSOLIDATION-PLAN P2/Q5, 2026-06-18). The
# pre-freeze whole-paper /rewrite consolidation LIFTS the prose freeze (the reviser reconciles
# numbers/citations/structure/theory across sections), keeping ONLY the light protection: the data/.bib
# denylist stays frozen and Write-on-manuscript is still blocked. Anti-fabrication of prose numbers is
# enforced POST-HOC by the provenance auditor (the hook cannot verify a DERIVED number), so the hook must
# NOT block a new number in prose under consolidate — which is exactly what distinguishes it from review.
# Run: bash tests/t31_consolidate_mode.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/plugins/paper-polish-ar/hooks/check_fidelity.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok() { echo "PASS  $1"; pass=$((pass+1)); }
no() { echo "FAIL  $1"; fail=$((fail+1)); }

mkdir -p "$TMP/.polish"; printf 'paper\n' > "$TMP/main.tex"; printf '@article{x}\n' > "$TMP/refs.bib"
mk_manifest() { # $1 = mode
  python3 - "$TMP/.polish/fidelity-manifest.json" "$TMP" "$1" <<'PY'
import json, sys, os
ws, mode = sys.argv[2], sys.argv[3]
m = {"mode": mode, "manuscripts": [os.path.join(ws, "main.tex")], "manuscript": os.path.join(ws, "main.tex"),
     "format": "latex", "denylist": [os.path.join(ws, "refs.bib")], "denylist_globs": ["*.bib"],
     "base_numbers": ["93.8"], "base_cite_keys": ["x"]}
open(sys.argv[1], "w").write(json.dumps(m))
PY
}
# returns "deny" if the hook denied, "allow" otherwise (allow() prints nothing or an allow JSON)
decide() { echo "$1" | CLAUDE_PROJECT_DIR="$TMP" python3 "$HOOK" | grep -q '"permissionDecision": "deny"' && echo deny || echo allow; }

EDIT_NUM='{"tool_name":"Edit","tool_input":{"file_path":"'"$TMP"'/main.tex","old_string":"paper","new_string":"paper acc 7.77 \\cite{newkey}"}}'
EDIT_BIB='{"tool_name":"Edit","tool_input":{"file_path":"'"$TMP"'/refs.bib","old_string":"@article{x}","new_string":"@article{y}"}}'
WRITE_MS='{"tool_name":"Write","tool_input":{"file_path":"'"$TMP"'/main.tex","content":"x"}}'

mk_manifest consolidate
[ "$(decide "$EDIT_NUM")" = allow ] && ok "consolidate: new number+cite in prose ALLOWED (post-hoc gated)" || no "consolidate blocked a prose number"
[ "$(decide "$EDIT_BIB")" = deny ]  && ok "consolidate: .bib denylist still frozen (DENY)"               || no "consolidate let a .bib edit through"
[ "$(decide "$WRITE_MS")" = deny ]  && ok "consolidate: Write-on-manuscript still blocked (DENY)"         || no "consolidate let a Write through"

# contrast: review mode blocks the very same new number (proves consolidate ≠ review)
mk_manifest review
[ "$(decide "$EDIT_NUM")" = deny ]  && ok "review: same new number is DENIED (consolidate ≠ review)"      || no "review failed to block a new number"

# absent manifest → no-op allow (proves the mode is opt-in)
rm -f "$TMP/.polish/fidelity-manifest.json"
[ "$(decide "$EDIT_BIB")" = allow ] && ok "no manifest → hook is a silent no-op"                          || no "hook denied with no manifest"

# ── review is DIAGNOSE-ONLY (39874f9), and since 2026-07-05 the vendored review.js is RETIRED in favor of the
#    REVIEW-OWNER protocol (spec/review-protocol.md + spec/review/). The D17 M1/M6/M7 mechanical matrices moved
#    OFF the reviewers onto the dedicated checklist pass (E-split) — assert they SURVIVE there; the retired
#    blessed-swap path must stay gone from the whole new review chain.
CHK="$ROOT/plugins/paper-polish-ar/spec/review/checklist-pass.md"
grepc() { grep -cE "$1" "$CHK" 2>/dev/null | tr -d ' '; }
echo "---- review protocol: diagnose-only kept-feature checks ----"
# the experiment blessed-swap unfreeze stays retired (no bless call anywhere in the review chain)
[ "$(cat "$ROOT/plugins/paper-polish-ar/spec/review-protocol.md" "$ROOT"/plugins/paper-polish-ar/spec/review/*.md | grep -cE 'exp_ledger\.py" bless|blessRecord\(')" = 0 ] && ok "review chain: blessed-swap path retired (no bless call)" || no "review chain: a bless call survived"
# M1/M6/M7 matrices survive on the checklist pass (E-split: off the reviewers, still guaranteed coverage)
[ "$(grepc 'experiment_coverage')" -ge 2 ] && ok "checklist-pass: experiment_coverage (M1 review-end spine)" || no "checklist-pass: experiment_coverage missing"
[ "$(grepc 'section_structure')" -ge 1 ] && [ "$(grepc 'caption_axis_fidelity')" -ge 1 ] && ok "checklist-pass: M7 section_structure + M6 caption_axis_fidelity matrices" || no "checklist-pass: M6/M7 matrices missing"

echo "----"
echo "T31: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
