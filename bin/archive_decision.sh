#!/usr/bin/env bash
# bin/archive_decision.sh — DETERMINISTIC archival of a resolved human gate (replaces the body-less
# archiveDecisionFile() that the LLM reproduced ad-hoc).
#
# WHY. The spec only described "mv DECISIONS-PENDING.md -> DECISIONS-RESOLVED-<n>.md" in a comment; the L0
# did it by hand and (this run) COPIED instead of MOVED -> a stale DECISIONS-PENDING.md lingered and the
# command re-reads it every turn (re-surface risk), and once archived an UNANSWERED template (RESOLVED-1).
# This makes the archive a real atomic move with a sentinel guard.
#
# - REFUSE (exit 2) if DECISIONS-PENDING.md is absent (nothing to archive).
# - REFUSE (exit 2) if the gate is UNANSWERED — its ANSWER line(s) still hold the `<leave blank; owner
#   fills ...>` sentinel (or are empty) AND no chat <answer_summary> was supplied. Never archive a blank gate.
# - else: n = (max index among existing DECISIONS-RESOLVED-*.md)+1 (gap-safe, NOT a count); stamp the RESOLVED header; write
#   DECISIONS-RESOLVED-<n>.md; then REMOVE DECISIONS-PENDING.md (atomic move — no stale file can survive).
#
# Usage: bin/archive_decision.sh <decisions_dir> [<answer_summary>]
#   <decisions_dir> = PROJECT_DIR/state/decisions (the dir holding DECISIONS-PENDING.md)
#   exit 0 = archived, exit 2 = error (no pending / unanswered / write failure).
set -euo pipefail

DDIR="${1:-}"; SUMMARY="${2:-}"
[ -n "$DDIR" ] || { echo "ERROR archive_decision: need <decisions_dir>"; exit 2; }
PENDING="$DDIR/DECISIONS-PENDING.md"
[ -f "$PENDING" ] || { echo "ERROR archive_decision: no DECISIONS-PENDING.md in $DDIR (nothing to archive)"; exit 2; }
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

OUT="$(DDIR="$DDIR" PENDING="$PENDING" SUMMARY="$SUMMARY" NOW="$NOW" python3 - <<'PY'
import os, sys, re, glob

ddir = os.environ["DDIR"]; pending = os.environ["PENDING"]
summary = os.environ["SUMMARY"].strip(); now = os.environ["NOW"]
text = open(pending, encoding="utf-8").read()

# UNANSWERED guard: every ANSWER line still the blank sentinel / empty, AND no chat summary -> refuse.
ans = re.findall(r"(?im)^\*\*ANSWER:\*\*\s*(.*)$", text)
def is_blank(a):
    a = a.strip()
    return (a == "") or ("leave blank" in a.lower()) or (a.startswith("<") and a.endswith(">"))
all_blank = (not ans) or all(is_blank(a) for a in ans)
if all_blank and not summary:
    print("ERROR archive_decision: gate is UNANSWERED (ANSWER still the <leave blank> sentinel and no chat "
          "answer supplied) — refusing to archive a blank gate", file=sys.stderr)
    sys.exit(2)

# deterministic next index
existing = glob.glob(os.path.join(ddir, "DECISIONS-RESOLVED-*.md"))
nums = []
for p in existing:
    m = re.search(r"DECISIONS-RESOLVED-(\d+)\.md$", p)
    if m: nums.append(int(m.group(1)))
n = (max(nums) + 1) if nums else 1
dest = os.path.join(ddir, "DECISIONS-RESOLVED-%d.md" % n)

# stamp the RESOLVED header
out = text
out = re.sub(r"(?s)^<!--.*?-->",
             "<!--\nauto-research DECISION FILE — RESOLVED (archived by bin/archive_decision.sh)\n-->",
             out, count=1) if out.lstrip().startswith("<!--") else \
      "<!--\nauto-research DECISION FILE — RESOLVED (archived by bin/archive_decision.sh)\n-->\n\n" + out
out = re.sub(r"(?im)^#\s+DECISION REQUIRED", "# DECISION RESOLVED", out, count=1)
stamp = "\n\n---\n**Resolved:** %s (bin/archive_decision.sh)\n" % now
if summary:
    stamp += "**RESOLVED ANSWER (chat, wins on conflict):** %s\n" % summary
out = out.rstrip() + stamp

tmp = dest + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    f.write(out)
os.replace(tmp, dest)          # atomic create of the RESOLVED file
os.remove(pending)             # THEN remove PENDING — no stale file can survive an archive
print(os.path.basename(dest))
PY
)" || { echo "$OUT"; exit 2; }

echo "OK archive_decision: DECISIONS-PENDING.md -> $OUT"

# best-effort deterministic event (observability; never blocks). decisions dir = DATA_ROOT/state/decisions.
DATA_ROOT="$(cd "$DDIR/../.." 2>/dev/null && pwd || true)"
[ -n "$DATA_ROOT" ] && CLAUDE_PROJECT_DIR="$DATA_ROOT" bash "$(dirname "${BASH_SOURCE[0]}")/log_event.sh" \
  decision_archived "{\"resolved\":\"$OUT\"}" 2>/dev/null || true
