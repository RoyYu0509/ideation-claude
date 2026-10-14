#!/usr/bin/env bash
# T24 — open-items ledger schema + close/reopen contract (Doc A §2.1/§8.2, Doc C §5.2 #5). Static check that
# the task-ledger skill pins the demand-driven, NON-monotone state machine (open/closed/reopened/deferred) +
# the close predicate (verify PASS ∧ B3 EXIT). The schema moved to references/open-concerns-schema.md
# (dossier-12 H2 split, 2026-07-06) — the grep target follows the content; SKILL.md keeps a pointer that a
# separate check below pins. The behavioral "inject a regression → item auto-reopens + its reference
# reloads" test is the live item NEXT-REVIEW C11.
# Run: bash tests/t24_ledger_open_reopen.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LED="$ROOT/plugins/paper-polish-ar/skills/task-ledger/references/open-concerns-schema.md"
SKILL="$ROOT/plugins/paper-polish-ar/skills/task-ledger/SKILL.md"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

chk "task-ledger defines the open-items schema"          "grep -qiF 'open-items' '$LED'"
for s in open closed reopened deferred; do
  chk "status '$s' in the state machine"                 "grep -qiwF '$s' '$LED'"
done
chk "NON-monotone (reopened behaves like open)"          "grep -qiE 'non-monoton|never just shrink|reopen' '$LED'"
chk "close predicate = verify PASS ∧ B3 EXIT"            "grep -qF 'verify PASS' '$LED' && grep -qF 'B3 EXIT' '$LED'"
chk "dimension-agnostic (serves both ledgers)"           "grep -qiF 'dimension-agnostic' '$LED'"
chk "concern field links to the reference map"           "grep -qF 'concern-reference-map.yaml' '$LED'"
chk "resident sensors run every round (reopen source)"   "grep -qiE 'resident sensor' '$LED'"
chk "SKILL.md keeps a live pointer to the split-out schema leaf" "grep -qF 'references/open-concerns-schema.md' '$SKILL' && grep -qF 'open_concerns' '$SKILL'"

echo "----"; echo "t24_ledger_open_reopen: $pass passed, $fail failed"; [ "$fail" = 0 ]
