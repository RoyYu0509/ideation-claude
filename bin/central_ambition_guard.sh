#!/usr/bin/env bash
# central_ambition_guard.sh — the MID-LOOP central/GAMBLE-K disposition guard.
#
# WHY: research-rescue was wired ONLY at verify_final's §4c reconciliation and the per-wave viability gate --
# both end-of-loop-ish checkpoints. A TASK_STATUS.concerns.json status write for a K backing
# HANDOFF.ambition.locked.json's central_result/GAMBLE set can narrow the claim MID-MILESTONE (a B1 hard-stop
# resumed on a free-text owner "descope" answer never touches research-rescue at all -- the exact gap the
# 2026-07-16 gate-invariant-relaxed-speculative-decoding run hit: K1 -> "descoped_infeasible_at_scale" via
# DECISIONS-RESOLVED-17 mid EXPERIMENTS_DONE, zero rescue spawned). This makes the omission mechanically
# detectable: a central K's row moving to a NON-CANONICAL status (open|closed|reopened|deferred is the whole
# enum, per task-ledger's open-concerns-schema.md), or a "closed" row whose OWN resolution text narrates a
# narrow, since this round STARTED, with no rescue verdict on disk for it -- is flagged.
#
# CENTRAL-K DETECTION (union, not intersection -- a false positive costs one extra cheap rescue; a false
# negative repeats the incident):
#   (a) every "<K-id>": block in HANDOFF.scale-contract.locked.json tagged `tag: GAMBLE`
#   (b) every K-id token (\bK[0-9]+\b) named in HANDOFF.ambition.locked.json's central_result block
#
# Usage: bin/central_ambition_guard.sh check <ws> <round> [--live-file <path>]
#   --live-file lets a caller (the PreToolUse hook) check a PROPOSED write before it lands, instead of the
#   on-disk TASK_STATUS.concerns.json (default).
#   Prints ONE line: "OK" or "NEEDS_RESCUE <csv of K-ids>". Exit 0 always (a detector never blocks itself);
#   exit 2 = bad args.
set -euo pipefail
CMD="${1:-}"; WS="${2:-}"; RND="${3:-}"
[ "$CMD" = "check" ] && [ -n "$WS" ] && [ -n "$RND" ] || { echo "ERROR central_ambition_guard: usage: $0 check <ws> <round> [--live-file <path>]" >&2; exit 2; }
shift 3 || true
LIVE=""
if [ "${1:-}" = "--live-file" ]; then LIVE="${2:-}"; fi

WS="$WS" RND="$RND" LIVE="$LIVE" python3 - <<'PY'
import os, re, json, sys

ws = os.environ["WS"]; rnd = os.environ["RND"]; live_override = os.environ.get("LIVE") or None
amb_p    = os.path.join(ws, "HANDOFF.ambition.locked.json")
sc_p     = os.path.join(ws, "HANDOFF.scale-contract.locked.json")
live_p   = live_override or os.path.join(ws, "TASK_STATUS.concerns.json")
before_p = os.path.join(ws, f".round-{rnd}.concerns.json")
rv_p     = os.path.join(ws, f".round-{rnd}.rescue-verdicts.json")

def content_of(p):
    try: return (json.loads(open(p, encoding="utf-8").read()) or {}).get("content") or ""
    except Exception: return ""

def rows_of(p):
    try: return (json.loads(open(p, encoding="utf-8").read()) or {}).get("open_concerns") or []
    except Exception: return []

if not os.path.isfile(amb_p):
    print("OK"); sys.exit(0)     # contract not locked yet (pre-Phase-0(C) / legacy run) -- do-no-harm

amb_txt = content_of(amb_p)
sc_txt  = content_of(sc_p) if os.path.isfile(sc_p) else ""

central = set()
for m in re.finditer(r'"?(K[0-9]+)"?:\s*\n(?:.*\n){0,15}?\s*tag:\s*GAMBLE\b', sc_txt):
    central.add(m.group(1))
cr = re.search(r'central_result:\s*\n((?:\s{4,}.*\n)+)', amb_txt)
if cr:
    for m in re.finditer(r'\bK[0-9]+\b', cr.group(1)):
        central.add(m.group(0))
if not central:
    print("OK"); sys.exit(0)

CANON = {"open", "closed", "reopened", "deferred"}
NARROW_RE = re.compile(r'descop|narrow|not.?retain|infeasible.?at.?scale|out.?of.?scope|redirect.?down|\bkill\b', re.I)

before = {r.get("id"): r for r in rows_of(before_p) if isinstance(r, dict)}
live   = {r.get("id"): r for r in rows_of(live_p)   if isinstance(r, dict)}

# scenario-agnostic: ANY rescue attempt on record for this K this round satisfies the precondition -- the
# guard cares THAT rescue ran (whichever gate spawned it: ours, verify_final's, or viability's), not WHICH.
already_rescued = set()
try:
    for v in (json.loads(open(rv_p, encoding="utf-8").read()) or []):
        if v.get("item"): already_rescued.add(v["item"])
except Exception:
    pass

flagged = []
for kid in sorted(central):
    lv = live.get(kid)
    if not lv: continue
    bf = before.get(kid); b_status = (bf or {}).get("status"); l_status = lv.get("status")
    hit = False
    if l_status not in CANON and l_status != b_status:
        hit = True                                    # bespoke out-of-taxonomy disposition, newly written this round
    elif b_status in ("open", "reopened") and l_status == "closed" and NARROW_RE.search(str(lv.get("resolution") or "")):
        hit = True                                    # canonically "closed" but the resolution text narrates a narrow
    if hit and kid not in already_rescued:
        flagged.append(kid)

print("NEEDS_RESCUE " + ",".join(flagged) if flagged else "OK")
PY
