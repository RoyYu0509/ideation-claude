#!/usr/bin/env bash
# T42 — bin/archive_decision.sh: the DETERMINISTIC atomic gate archival that replaces the body-less
# archiveDecisionFile() the LLM reproduced ad-hoc (this run: COPY-not-move -> stale PENDING; archived an
# UNANSWERED template -> RESOLVED-1). Run: bash tests/t42_archive_decision.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARC="$ROOT/bin/archive_decision.sh"; TPL="$ROOT/assets/decision-file-template.md"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
DD="$TMP/state/decisions"; mkdir -p "$DD"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

# 1) no PENDING => exit 2
bash "$ARC" "$DD" >/dev/null 2>&1; [ $? -eq 2 ] && ok "no DECISIONS-PENDING.md => exit 2" || no "absent pending not refused"

# 2) UNANSWERED pending (template sentinel) + no chat summary => exit 2, PENDING untouched
cp "$TPL" "$DD/DECISIONS-PENDING.md"
bash "$ARC" "$DD" >/dev/null 2>&1; rc=$?
[ $rc -eq 2 ] && [ -f "$DD/DECISIONS-PENDING.md" ] && [ ! -f "$DD/DECISIONS-RESOLVED-1.md" ] \
  && ok "UNANSWERED gate refused (exit 2), nothing archived" || no "UNANSWERED gate archived (the RESOLVED-1 bug)"

# 3) answered via chat summary => OK, RESOLVED-1 created, PENDING REMOVED (atomic move, no stale file)
bash "$ARC" "$DD" "A — proceed" >/dev/null 2>&1 \
  && [ -f "$DD/DECISIONS-RESOLVED-1.md" ] && [ ! -f "$DD/DECISIONS-PENDING.md" ] \
  && ok "answered gate -> RESOLVED-1, PENDING removed (no stale re-surface)" || no "archive did not atomically move"

# 4) RESOLVED header stamped + chat answer recorded
grep -q "DECISION RESOLVED" "$DD/DECISIONS-RESOLVED-1.md" && grep -q "A — proceed" "$DD/DECISIONS-RESOLVED-1.md" \
  && ok "RESOLVED header + chat answer stamped" || no "RESOLVED stamping missing"

# 5) deterministic next index: a 2nd answered gate -> RESOLVED-2 (not overwrite -1)
cp "$TPL" "$DD/DECISIONS-PENDING.md"
bash "$ARC" "$DD" "B" >/dev/null 2>&1
[ -f "$DD/DECISIONS-RESOLVED-2.md" ] && ok "second archive -> RESOLVED-2 (deterministic index)" || no "index not incremented"

# 6) answered IN-FILE (ANSWER line edited, no chat summary) => archived
cp "$TPL" "$DD/DECISIONS-PENDING.md"
# replace the sentinel ANSWER line with a real answer
python3 - "$DD/DECISIONS-PENDING.md" <<'PY'
import sys,re
p=sys.argv[1]; t=open(p).read()
t=re.sub(r'(?m)^\*\*ANSWER:\*\*.*$', '**ANSWER:** A', t)
open(p,'w').write(t)
PY
bash "$ARC" "$DD" >/dev/null 2>&1 && [ -f "$DD/DECISIONS-RESOLVED-3.md" ] && [ ! -f "$DD/DECISIONS-PENDING.md" ] \
  && ok "in-file answer (no chat) archived -> RESOLVED-3" || no "in-file answer not archived"

echo "----"; echo "t42_archive_decision: $pass passed, $fail failed"; [ "$fail" = 0 ]
