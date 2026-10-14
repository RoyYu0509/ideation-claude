#!/usr/bin/env bash
# bin/derive_gate_input.sh — RC-4: build the B3 loop-gate input from DISK GROUND TRUTH, not from the
# reviewed agent's self-report. The three gate fields are RE-DERIVED here; the envelope's self-reported
# values are recorded ALONGSIDE as `claimed`, and any disagreement is flagged (the tell that an envelope
# under-reported a science change — P3 r3: 6 numbers changed on disk while the envelope said wb=0).
#
# Usage:
#   bin/derive_gate_input.sh <ws> <round> <paper_baseline_sha> <claimed_risk> <claimed_nh> <claimed_wb> <out.json>
#
# Derivations:
#   overall_risk      <- parse <ws>/paper/review-report.md "Overall risk:" line (re-read by L0 itself)
#   new_handoff_items <- count <ws>/HANDOFF-*.md newer than the <ws>/.round-<round>.start marker
#   write_backs       <- 1 if ANY .tex line in <ws>/paper changed since <paper_baseline_sha> else 0
#                        (STRICTER than the old experiment-only count — this is what catches a theorem
#                         rewrite or 6 swapped decimals reported as wb=0; STAGES first so a brand-new
#                         UNTRACKED .tex — a table/appendix/section written back this round with no
#                         intervening milestone commit — is counted too, not silently missed by a
#                         tracked-only diff, which would re-open the RC-4 fail-open it exists to close)
#
# Writes <out.json> with TOP-LEVEL { round, overall_risk, new_handoff_items, write_backs } (what
# loop_gate.sh reads) PLUS { derived:{...}, claimed:{...}, mismatch:bool } for audit. Prints "MISMATCH ..."
# to stdout when derived != claimed (L0 surfaces it). Exits 2 on un-derivable risk or a missing baseline
# (fail loud — never fall back to a value that could ship a fresh draft as a clean exit).
set -euo pipefail

WS="${1:-}"; ROUND="${2:-}"; BASE="${3:-}"; CRISK="${4:-}"; CNH="${5:-0}"; CWB="${6:-0}"; OUT="${7:-}"
[ -n "$WS" ] && [ -n "$ROUND" ] && [ -n "$OUT" ] || {
  echo "ERROR derive_gate_input: usage <ws> <round> <paper_baseline_sha> <claimed_risk> <claimed_nh> <claimed_wb> <out.json>"; exit 2; }
[ -d "$WS" ] || { echo "ERROR derive_gate_input: workspace not found: $WS"; exit 2; }

# --- derived overall_risk: parse the review report (the SAME file the L1 wrote, but L0 re-reads it) ------
REP="$WS/paper/review-report.md"
DRISK=""
if [ -f "$REP" ]; then
  # Anchor the verdict to the overall_risk FIELD VALUE — the token that immediately FOLLOWS
  # `overall[ _]risk` + an optional quote/bold marker + a colon (`:` or full-width `：`) + optional
  # quote/bold marker. The prior loose match (`grep -iE 'overall[ _]risk' | grep -ioE '(verdict)'`) was
  # FAIL-OPEN: renderReviewReport() serializes paper_model / pinned_contribution prose BEFORE the
  # overall_risk field, so a prose line that merely MENTIONS "overall risk" and carries a verdict
  # SUBSTRING elsewhere — e.g. "reduces the overall risk of un**accept**able constraint violation" —
  # yielded `accept` (substring of "unacceptable") even when the true field value was `reject`, shipping
  # a paper the B3 gate should have looped. Requiring the token to be the field VALUE (not any token on
  # any line mentioning risk) ignores such shadow prose; a genuinely value-less report still yields an
  # empty DRISK and hard-exits 2 below. Handles both the real JSON emit (`"overall_risk": "reject"`) and
  # a hand-written markdown/plain digest (`**Overall risk:** reject`, `overall_risk: reject`).
  DRISK="$(grep -ioE 'overall[ _]risk[*"]*[[:space:]]*[:：][[:space:]]*[*"]*[[:space:]]*(reject|major_revision|minor_revision|accept)' "$REP" | grep -ioE '(reject|major_revision|minor_revision|accept)' | head -1 | tr '[:upper:]' '[:lower:]' || true)"
fi
[ -n "$DRISK" ] || { echo "ERROR derive_gate_input: cannot derive overall_risk from $REP (no parseable 'Overall risk:' line) — refusing to trust the envelope"; exit 2; }

# --- derived new_handoff_items: HANDOFF-*.md exported THIS round (newer than the round-start marker) -----
MARK="$WS/.round-${ROUND}.start"
if [ -f "$MARK" ]; then
  DNH="$(find "$WS" -maxdepth 1 -name 'HANDOFF-*.md' -newer "$MARK" 2>/dev/null | wc -l | tr -d ' ')"
else
  DNH="$(find "$WS" -maxdepth 1 -name 'HANDOFF-*.md' 2>/dev/null | wc -l | tr -d ' ')"
fi

# --- derived write_backs: did ANY .tex change in paper/ since the round baseline commit (git ground truth)
[ -n "$BASE" ] || { echo "ERROR derive_gate_input: empty paper baseline sha — cannot derive write_backs honestly"; exit 2; }
git -C "$WS/paper" rev-parse --verify -q "$BASE^{commit}" >/dev/null 2>&1 || {
  echo "ERROR derive_gate_input: paper baseline '$BASE' is not a valid commit in $WS/paper"; exit 2; }
# STAGE before diffing: `git diff <BASE>` sees only TRACKED changes, so a brand-new UNTRACKED .tex (a new
# table/appendix/section written back this round, with no intervening B1 milestone commit to track it) would
# derive write_backs=0 and silently PASS the loop-exit gate — the exact fail-open this disk derivation exists
# to catch. `git add -A` makes the untracked file visible; `git diff --cached "$BASE"` then counts it (its
# full content as added lines). Staging is safe: round_baseline_paper is captured from HEAD — a commit, not
# the index (research.js loop ~line 790) — and both successor paths (ship→batchGroundClean, the next round's
# runB1) `git add -A && commit` regardless, so the index is re-derived and never surprises a later L0 commit.
# A staging FAILURE fails loud (exit 2) — never fall back to the untracked-blind diff (= a fresh-draft clean exit).
git -C "$WS/paper" add -A >/dev/null 2>&1 || {
  echo "ERROR derive_gate_input: 'git add -A' failed in $WS/paper — cannot derive write_backs honestly"; exit 2; }
DWB_LINES="$(git -C "$WS/paper" diff --cached --numstat "$BASE" -- '*.tex' 2>/dev/null | awk '{a+=$1; d+=$2} END{print (a+d)+0}')"

OUT="$OUT" ROUND="$ROUND" DRISK="$DRISK" DNH="$DNH" DWB_LINES="$DWB_LINES" \
CRISK="$CRISK" CNH="$CNH" CWB="$CWB" python3 - <<'PY'
import os, json
rnd   = int(os.environ["ROUND"])
drisk = os.environ["DRISK"]
dnh   = int(os.environ["DNH"] or 0)
dwbl  = int(os.environ["DWB_LINES"] or 0)
dwb   = 1 if dwbl > 0 else 0                          # write_backs is a "did the science change this round" flag
crisk = (os.environ.get("CRISK") or "").strip().lower()
cnh   = int(os.environ.get("CNH") or 0)
cwbc  = int(os.environ.get("CWB") or 0)
cwb   = 1 if cwbc > 0 else 0
# [unified-loop] write_backs is NO LONGER a mismatch signal: the DRAFT stage rewrites the whole paper every
# round, so the paper-diff (dwb) is large BY DESIGN and would always disagree with the review's wb=0. Mismatch
# now gates ONLY on the two signals the review agent actually controls: overall_risk and new_handoff_items.
mismatch = (drisk != crisk) or (dnh != cnh)
rec = {"round": rnd, "overall_risk": drisk, "new_handoff_items": dnh, "write_backs": dwb,
       "derived": {"overall_risk": drisk, "new_handoff_items": dnh,
                   "write_backs": dwb, "write_backs_lines_changed": dwbl},
       "claimed": {"overall_risk": crisk, "new_handoff_items": cnh, "write_backs": cwbc},
       "mismatch": bool(mismatch)}
json.dump(rec, open(os.environ["OUT"], "w"), indent=2)
if mismatch:
    print("MISMATCH derive_gate_input: derived(risk=%s nh=%d wb=%d) != claimed(risk=%s nh=%d wb=%d) — "
          "L0 MUST surface this (envelope under-reported a disk change)." % (drisk, dnh, dwb, crisk, cnh, cwb))
else:
    print("OK derive_gate_input: derived == claimed (risk=%s nh=%d wb=%d)" % (drisk, dnh, dwb))
PY

# 统一回收 (logging side-channel; NEVER affects the gate decision computed above): mirror the derived
# gate-input record (round/risk/nh/wb + derived/claimed/mismatch) into the unified event stream so a B3
# MISMATCH is one grep away. Fail-open — a logging hiccup must not break the gate.
LE_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
[ -f "$OUT" ] && bash "$LE_ROOT/bin/log_event.sh" gate_input_derived "$(cat "$OUT")" 2>/dev/null || true
