#!/usr/bin/env bash
# t9 — bin/derive_gate_input.sh derives the B3 gate inputs from DISK and flags a self-report mismatch (RC-4).
# [unified-loop 2026-06-20] write_backs is now INFORMATIONAL (the DRAFT stage rewrites the whole paper every
# round): it is still DERIVED + recorded for audit, but mismatch gates ONLY on overall_risk + new_handoff_items.
# (The drafter's numbers are guarded by the focused verifier — V6 artifact-sync + code-audit — not by this diff.) Run standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
chk(){ if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
G="git -c user.email=t@e -c user.name=t"

ws="$TMP/ws"; mkdir -p "$ws/paper"
printf '**Overall risk:** minor_revision\n' > "$ws/paper/review-report.md"
printf '\\documentclass{article}\\begin{document}x=1\\end{document}\n' > "$ws/paper/master.tex"
( cd "$ws/paper" && $G init -q && $G add -A && $G commit -qm baseline )
BASE="$(git -C "$ws/paper" rev-parse HEAD)"
touch "$ws/.round-1.start"

# Case 1: nothing changed since baseline, claimed matches -> no mismatch, write_backs 0
chk "clean round, claimed==derived -> OK, no MISMATCH" \
  "out=\$(bash '$ROOT/bin/derive_gate_input.sh' '$ws' 1 '$BASE' minor_revision 0 0 '$ws/g1.json' 2>&1); echo \"\$out\" | grep -q '^OK' && python3 -c \"import json;d=json.load(open('$ws/g1.json'));assert d['overall_risk']=='minor_revision' and d['write_backs']==0 and d['new_handoff_items']==0 and d['mismatch']==False\""

# Case 2: [unified-loop] the DRAFT stage rewrites the whole paper EVERY round, so a paper change is EXPECTED and
# write_backs is NO LONGER a mismatch signal — derived wb=1 is still RECORDED, but mismatch=False when risk + nh match.
printf 'CHANGED NUMBER 120601\n' >> "$ws/paper/master.tex"
chk "paper changed (drafter rewrite) -> write_backs=1 RECORDED but NO mismatch" \
  "out=\$(bash '$ROOT/bin/derive_gate_input.sh' '$ws' 1 '$BASE' minor_revision 0 0 '$ws/g2.json' 2>&1); echo \"\$out\" | grep -q '^OK' && python3 -c \"import json;d=json.load(open('$ws/g2.json'));assert d['write_backs']==1 and d['mismatch']==False\""

# Case 3: a new HANDOFF-*.md exported this round but claim nh=0 -> derived nh>=1, MISMATCH
sleep 1; printf 'new exhibit\n' > "$ws/HANDOFF-newexhibit.md"
chk "new HANDOFF-*.md but claimed nh=0 -> MISMATCH + derived nh>=1" \
  "bash '$ROOT/bin/derive_gate_input.sh' '$ws' 1 '$BASE' minor_revision 0 1 '$ws/g3.json' >/dev/null 2>&1; python3 -c \"import json;d=json.load(open('$ws/g3.json'));assert d['new_handoff_items']>=1 and d['mismatch']==True\""

# Case 4: empty baseline -> fail loud exit 2 (never fall back to a value that could ship a fresh draft)
chk "empty paper baseline -> exit 2" "! bash '$ROOT/bin/derive_gate_input.sh' '$ws' 1 '' minor_revision 0 0 '$ws/g4.json' >/dev/null 2>&1"

# Case 5: un-derivable overall_risk (no report) -> exit 2 (refuse to trust the envelope)
ws2="$TMP/ws2"; mkdir -p "$ws2/paper"; ( cd "$ws2/paper" && $G init -q && $G commit -qm e --allow-empty )
B2="$(git -C "$ws2/paper" rev-parse HEAD)"
chk "no parseable overall_risk -> exit 2" "! bash '$ROOT/bin/derive_gate_input.sh' '$ws2' 1 '$B2' minor_revision 0 0 '$ws2/g5.json' >/dev/null 2>&1"

# Case 6: a NEW UNTRACKED .tex at paper ROOT. The derivation still STAGES untracked files so they COUNT in the
# derived write_backs (=1, RECORDED for audit), but [unified-loop] wb no longer drives mismatch -> mismatch=False.
# FRESH CLEAN workspace so the untracked file is the ONLY change since baseline (tracked tree is pristine).
ws3="$TMP/ws3"; mkdir -p "$ws3/paper"
printf '**Overall risk:** minor_revision\n' > "$ws3/paper/review-report.md"
printf '\\documentclass{article}\\begin{document}x=1\\end{document}\n' > "$ws3/paper/master.tex"
( cd "$ws3/paper" && $G init -q && $G add -A && $G commit -qm baseline )
B3="$(git -C "$ws3/paper" rev-parse HEAD)"
touch "$ws3/.round-1.start"
printf '\\begin{table}new appendix table written back this round\\end{table}\n' > "$ws3/paper/new-table.tex"  # UNTRACKED, root
chk "new UNTRACKED .tex at paper root -> write_backs=1 RECORDED but NO mismatch" \
  "bash '$ROOT/bin/derive_gate_input.sh' '$ws3' 1 '$B3' minor_revision 0 0 '$ws3/g6.json' >/dev/null 2>&1; python3 -c \"import json;d=json.load(open('$ws3/g6.json'));assert d['write_backs']==1 and d['mismatch']==False and d['new_handoff_items']==0\""

# Case 7: same hole, NESTED path — a NEW UNTRACKED .tex under sections/ (proves the '*.tex' pathspec matches
# subdirectories, so a fix that only stages root .tex would still fail here). FRESH CLEAN workspace.
ws4="$TMP/ws4"; mkdir -p "$ws4/paper/sections"
printf '**Overall risk:** minor_revision\n' > "$ws4/paper/review-report.md"
printf '\\documentclass{article}\\begin{document}x=1\\end{document}\n' > "$ws4/paper/master.tex"
( cd "$ws4/paper" && $G init -q && $G add -A && $G commit -qm baseline )
B4="$(git -C "$ws4/paper" rev-parse HEAD)"
touch "$ws4/.round-1.start"
printf '\\section{New}a written-back appendix section\n' > "$ws4/paper/sections/new-appendix.tex"  # UNTRACKED, sections/
chk "new UNTRACKED .tex in sections/ -> write_backs=1 RECORDED but NO mismatch ('*.tex' matches subdirs)" \
  "bash '$ROOT/bin/derive_gate_input.sh' '$ws4' 1 '$B4' minor_revision 0 0 '$ws4/g7.json' >/dev/null 2>&1; python3 -c \"import json;d=json.load(open('$ws4/g7.json'));assert d['write_backs']==1 and d['mismatch']==False and d['new_handoff_items']==0\""

# Case 8: SHADOW header regression — the REAL review-report.md (JSON from review.js renderReviewReport)
# dumps paper_model prose BEFORE the "overall_risk" verdict key, so a token-less line matching
# 'overall risk' (here: a supporting-claim prose line "reduces the overall risk of …") PRECEDES the real
# verdict line. Anchoring the token to the FIELD VALUE (the verdict that follows 'overall_risk' + colon)
# ignores the shadow prose and derives the real verdict one line down (major_revision) -> exit 0
# (never the empty-risk hard-exit 2 that a blind head-of-first-mention would have caused).
ws5="$TMP/ws5"; mkdir -p "$ws5/paper"
printf '%s\n' \
  '{' \
  '  "diagnose_only": true,' \
  '  "paper_model": {' \
  '    "supporting_claims": [' \
  '      "the proposed controller reduces the overall risk of constraint violation under disturbance"' \
  '    ]' \
  '  },' \
  '  "overall_risk": "major_revision",' \
  '  "meta_review": "borderline; needs a stronger baseline"' \
  '}' > "$ws5/paper/review-report.md"
printf '\\documentclass{article}\\begin{document}x=1\\end{document}\n' > "$ws5/paper/master.tex"
( cd "$ws5/paper" && $G init -q && $G add -A && $G commit -qm baseline )
B5="$(git -C "$ws5/paper" rev-parse HEAD)"
touch "$ws5/.round-1.start"
chk "token-less 'overall risk' shadow line before verdict -> derives major_revision (exit 0), NOT exit 2" \
  "out=\$(bash '$ROOT/bin/derive_gate_input.sh' '$ws5' 1 '$B5' major_revision 0 0 '$ws5/g8.json' 2>&1); echo \"\$out\" | grep -q '^OK' && python3 -c \"import json;d=json.load(open('$ws5/g8.json'));assert d['overall_risk']=='major_revision' and d['mismatch']==False\""

# Case 9: TOKEN-BEARING SHADOW regression (the fail-open the adversarial review demonstrated live). Same
# real JSON emit as Case 8, but the paper_model prose line now carries a VERDICT SUBSTRING — "reduces the
# overall risk of unacceptable ..." embeds 'accept' inside "unacceptable" — and it is serialized BEFORE
# the real field. The old one-stage derivation (grep -iE 'overall[ _]risk' | grep -ioE '(verdict)' | head -1)
# matched that prose line first and extracted 'accept' — a FALSE clean-exit verdict shipping a paper whose
# true field value is 'reject'. The anchored fix requires the token to be the FIELD VALUE (following
# 'overall_risk' + colon), so the shadow prose is ignored and 'reject' is derived. This case DERIVES the
# wrong 'accept' against the old code and the correct 'reject' against the fix (verified both directions).
ws6="$TMP/ws6"; mkdir -p "$ws6/paper"
printf '%s\n' \
  '{' \
  '  "diagnose_only": true,' \
  '  "paper_model": {' \
  '    "supporting_claims": [' \
  '      "the proposed controller reduces the overall risk of unacceptable constraint violation under disturbance"' \
  '    ]' \
  '  },' \
  '  "pinned_contribution": "an accept/reject-agnostic estimator of the overall risk of miscoverage",' \
  '  "overall_risk": "reject",' \
  '  "meta_review": "central identifiability claim is unsupported by the linear-only experiments"' \
  '}' > "$ws6/paper/review-report.md"
printf '\\documentclass{article}\\begin{document}x=1\\end{document}\n' > "$ws6/paper/master.tex"
( cd "$ws6/paper" && $G init -q && $G add -A && $G commit -qm baseline )
B6="$(git -C "$ws6/paper" rev-parse HEAD)"
touch "$ws6/.round-1.start"
chk "token-bearing shadow ('...overall risk of unacceptable...') before real verdict -> derives reject, NOT accept" \
  "out=\$(bash '$ROOT/bin/derive_gate_input.sh' '$ws6' 1 '$B6' reject 0 0 '$ws6/g9.json' 2>&1); echo \"\$out\" | grep -q '^OK' && python3 -c \"import json;d=json.load(open('$ws6/g9.json'));assert d['overall_risk']=='reject' and d['mismatch']==False\""

# ── Loop-visible artifact PINNING (static spec assertions) ───────────────────────────────────────────
# The gate readers above scan <WS>/paper/review-report.md and <WS>/HANDOFF-*.md (root, maxdepth 1). Assert the
# two producers agree on those locations: (a) the L0 review contract pins both paths; (b) the review protocol's
# output contract pins the HANDOFF at the WORKSPACE ROOT (the parent of the paper dir), report at the paper dir.
CONTRACT="$ROOT/spec/spawn-prompts/REVIEW-L0-CONTRACT.md"
REVIEWOC="$ROOT/plugins/paper-polish-ar/spec/review/output-contract.md"
schk(){ d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS  $d"; pass=$((pass+1)); else echo "FAIL  $d"; fail=$((fail+1)); fi; }
snot(){ d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "FAIL  $d"; fail=$((fail+1)); else echo "PASS  $d"; pass=$((pass+1)); fi; }

schk "contract pins review-report.md under paper/"            grep -Fq '<WS>/paper/review-report.md' "$CONTRACT"
schk "contract pins HANDOFF-*.md at workspace ROOT"           grep -Fq '<WS>/HANDOFF-*.md' "$CONTRACT"
schk "contract states HANDOFF root is NOT paper/"             grep -Fq 'workspace ROOT, NOT paper/' "$CONTRACT"
schk "output contract derives wsRoot = dirname(paperDir)"     grep -Fq 'dirname(paperDir)' "$REVIEWOC"
schk "output contract HANDOFF path is at the workspace root"  grep -Fq '<wsRoot>/HANDOFF-' "$REVIEWOC"
snot "output contract never puts HANDOFF under the paper dir" grep -Fq '<paperDir>/HANDOFF-' "$REVIEWOC"
schk "output contract report path uses the paper dir"         grep -Fq '<paperDir>/review-report.md' "$REVIEWOC"

echo "----"; echo "t9_gate_derive: $pass passed, $fail failed"; [ "$fail" = 0 ]
