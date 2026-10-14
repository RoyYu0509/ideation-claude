#!/usr/bin/env bash
# bin/ideation_progress.sh — DETERMINISTIC "is this week's ideation actually finished?" oracle.
#
# WHY THIS EXISTS. The 2026-W36 run stalled THREE times (10.1h + 4.0h + 1.0h = 88% of its 17.2h wall
# clock) because the ideation L1 spawned real child agents and then ENDED ITS OWN TURN to wait for them.
# A child's completion notification only reaches L0 — nothing wakes a middle-tier L1 — so the run sat
# dead until a human noticed. The rule against this was already written in three places
# (IDEATION-L0.md "NO SELF-REWAKE ... AWAIT every parallel batch within this turn",
# arxiv-scout-beta.md:139-144, spawn_guard.py's WAITER deny) and the L1 violated it anyway.
#
# The lesson this file encodes: L1 SELF-REPORTS ARE NOT EVIDENCE. Same root cause as the telemetry gap
# (101/101 agent_spawn events came from the hook, ZERO from the L0 that was supposed to log them):
# whatever depends on an LLM remembering a rule gets skipped; whatever a script checks is reliable.
# So L0 must not believe "I'm done" or "I'm waiting for X" — it runs THIS and believes the disk.
#
# CONTRACT (unlike log_event.sh's fail-open side channel, this IS read by control flow → FAIL LOUD):
#   line 1 = COMPLETE | INCOMPLETE <one-line summary> | ERROR <why>
#   exit   = 0 COMPLETE · 1 INCOMPLETE · 2 ERROR (missing ledger / unparseable / bad args)
#   Lines 2+ on INCOMPLETE are the gap detail, written to be pasted VERBATIM into the SendMessage that
#   wakes the stalled L1 — it should be able to act on them without re-deriving anything.
#
# TWO SCOPES:
#   (default)       the whole week is finished — settled papers + bundles + manifest + fresh digest/web.
#                   This is what L0 checks before it believes an ideation L1 has finished.
#   --corpus-only   only the SCIENCE RECORD an experiment corpus consumes — settled papers + a bundle.json
#                   behind every converged candidate. Deliberately ignores the manifest and the digest/web
#                   reports, because a frozen corpus does not contain them (build_cards.py reads the ledger
#                   and bundle.json, nothing else), so a stale report cannot make the corpus wrong. W36 is
#                   the proof: its reports were stale and its 292-file corpus was still fully valid.
#
# Usage: bin/ideation_progress.sh <PROJECT_DIR> <week> [--corpus-only]
set -u

DIR="${1:-}"; WEEK="${2:-}"; SCOPE="${3:-full}"
if [ -z "$DIR" ] || [ -z "$WEEK" ]; then
  echo "ERROR ideation_progress: usage: $0 <PROJECT_DIR> <week> [--corpus-only]"
  exit 2
fi
if [ "$SCOPE" != "full" ] && [ "$SCOPE" != "--corpus-only" ]; then
  echo "ERROR ideation_progress: unknown option '$SCOPE' (expected --corpus-only)"
  exit 2
fi

DIR="$DIR" WEEK="$WEEK" SCOPE="$SCOPE" python3 - <<'PY'
import json, os, sys

d           = os.environ["DIR"]
week        = os.environ["WEEK"]
corpus_only = os.environ.get("SCOPE") == "--corpus-only"

ledger_p = os.path.join(d, "data", "cache", f"week-{week}-ideation-ledger.json")
scout_p  = os.path.join(d, "data", "cache", f"week-{week}-scout.json")
digest_p = os.path.join(d, "data", "digests", f"{week}-scout.md")
web_p    = os.path.join(d, "data", "web", f"{week}-scout.html")

def die(msg):
    print(f"ERROR ideation_progress: {msg}")
    sys.exit(2)

if not os.path.exists(ledger_p):
    die(f"no ledger at {ledger_p} — ideation has not reached the ledger stage for {week}")
try:
    with open(ledger_p) as f:
        led = json.load(f)
except Exception as e:
    die(f"ledger unparseable ({ledger_p}): {e}")

papers = led.get("papers") or {}
if not papers:
    die(f"ledger has zero papers — {ledger_p} is a shell, not a finished week")

TERMINAL = {"converged", "exhausted_budget", "exhausted_honest"}
gaps, detail = [], []

# ── 1. every paper must have settled ────────────────────────────────────────────────────────────────
unsettled = sorted(a for a, ps in papers.items() if (ps.get("status") or "active") not in TERMINAL)
if unsettled:
    gaps.append(f"{len(unsettled)} paper(s) still active")
    detail.append("PAPERS NOT SETTLED (need generate→screen→verify→recheck to a terminal status):")
    for a in unsettled:
        detail.append(f"  - {a}: status={papers[a].get('status')!r} rounds_done={papers[a].get('rounds_done')}")

# ── 2. every converged candidate must have the bundle H2's cards are built from ─────────────────────
# (build_cards.py reads bundle.json's claim + premises.falsifier; a converged candidate without one is
#  a candidate the experiment corpus cannot use.)
missing_bundles = []
n_converged = 0
for aid, ps in papers.items():
    for key, c in (ps.get("candidates") or {}).items():
        if c.get("status") != "converged":
            continue
        n_converged += 1
        bdir = c.get("bundle_dir") or os.path.join(d, "data", "ideations", week, "bundles", f"{aid}-{key}")
        if not os.path.isabs(bdir):
            bdir = os.path.join(d, bdir)
        if not os.path.exists(os.path.join(bdir, "bundle.json")):
            missing_bundles.append(f"{aid}-{key}")
if missing_bundles:
    gaps.append(f"{len(missing_bundles)} converged candidate(s) missing bundle.json")
    detail.append("CONVERGED CANDIDATES WITHOUT bundle.json (H2 corpus cannot use these):")
    for cid in missing_bundles:
        detail.append(f"  - {cid}")

# ── checks 3-4 are WEEK-level, not corpus-level: a frozen corpus contains neither the manifest nor the
#    reports, so --corpus-only stops here (see the two-scope note in the header). ─────────────────────
if corpus_only:
    if gaps:
        print(f"INCOMPLETE {'; '.join(gaps)}")
        print()
        print(f"week={week}  papers={len(papers)}  converged_candidates={n_converged}  scope=corpus-only")
        for line in detail:
            print(line)
        sys.exit(1)
    print("COMPLETE")
    print(f"week={week}  papers={len(papers)}  converged_candidates={n_converged}  scope=corpus-only")
    sys.exit(0)

# ── 3. the manifest must have been written back (finalize ran) ──────────────────────────────────────
if not os.path.exists(scout_p):
    gaps.append("scout.json missing")
    detail.append(f"MANIFEST MISSING: {scout_p} — run the finalize + manifest write-back step.")
else:
    try:
        with open(scout_p) as f:
            scout = json.load(f)
        if not (scout.get("ideation_manifest") or []):
            gaps.append("ideation_manifest empty")
            detail.append(f"MANIFEST EMPTY: {scout_p} has no ideation_manifest — finalize did not write back.")
    except Exception as e:
        gaps.append("scout.json unparseable")
        detail.append(f"MANIFEST UNPARSEABLE: {scout_p}: {e}")

# ── 4. digest + web must have been re-rendered AFTER everything they describe ───────────────────────
# The baseline is max(ledger, newest refined/*.md), NOT the ledger alone. W36 is exactly why: the ledger
# settled 12:37:31Z, both reports rendered 12:41:20Z (4 min later — clean against the ledger), and then
# the plan stage wrote 7 refined seeds at 13:03:27Z. Neither report was re-rendered, so the web report
# still says "种子尚未生成" seven times about seven seeds that exist on disk. A ledger-only check calls
# that COMPLETE and ships a report that lies.
fresh_after = os.path.getmtime(ledger_p)
fresh_src   = "ledger"
refined_dir = os.path.join(d, "data", "ideations", week, "refined")
if os.path.isdir(refined_dir):
    for fn in os.listdir(refined_dir):
        if not fn.endswith(".md"):
            continue
        m = os.path.getmtime(os.path.join(refined_dir, fn))
        if m > fresh_after:
            fresh_after, fresh_src = m, f"refined/{fn}"

for label, p in (("digest", digest_p), ("web report", web_p)):
    if not os.path.exists(p):
        gaps.append(f"{label} missing")
        detail.append(f"{label.upper()} MISSING: {p} — re-render it from the final ledger.")
    elif os.path.getmtime(p) < fresh_after:
        gaps.append(f"{label} stale")
        detail.append(f"{label.upper()} STALE: {p} predates {fresh_src} — re-render it "
                      f"(a stale report misreports seeds/verdicts that already exist on disk).")

# ── verdict ────────────────────────────────────────────────────────────────────────────────────────
if gaps:
    print(f"INCOMPLETE {'; '.join(gaps)}")
    print()
    print(f"week={week}  papers={len(papers)}  converged_candidates={n_converged}")
    for line in detail:
        print(line)
    sys.exit(1)

print("COMPLETE")
print(f"week={week}  papers={len(papers)}  converged_candidates={n_converged}  ledger={ledger_p}")
sys.exit(0)
PY
