#!/usr/bin/env python3
"""Re-adjudicate a week's kills under the 2026-09 evidence rules, without
re-running a single agent.

The rules that changed (arxiv-verify SKILL Step 2): a premise may only be KILLED
on zero-simulation evidence — arithmetic on the paper's own published numbers, a
symbolic/analytic contradiction, or a refutation read off real released data.
Anything settled with a self-written simulator or a synthetic distribution is
now `deferred` and becomes a mandatory Phase-0 check downstream; an unavailable
asset is a scope constraint, not a death; a cost estimate is a resource fact;
and a broken verification ROUTE is `rescope`, not a dead direction.

This script replays those rules over an existing ledger. It classifies each
death mechanically, then lets a hand adjudication file override — because the
mechanical signals genuinely cannot separate the cases: a hand-rolled APFC
relaxation, a literature order-check, an inapplicable ground-truth test and a
spectrum-availability check all look identical to a static scan (no rng, no
sympy, no file read) while being four different verdicts.

It NEVER edits the ledger. The ledger is an append-only account of what actually
happened; this writes a parallel `replay/` tree recording what the same evidence
would decide today.

Usage:
    run_py.sh scripts/replay_kills.py --week 2026-W35 [--data-root DIR]
                                      [--adjudication FILE] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config  # noqa: E402

# Where a re-adjudicated candidate goes now.
DISPOSITIONS = {
    "uphold":       "kill stands — zero-simulation evidence",
    "surrogate":    "premise -> deferred (Phase-0 check); the killing number came from an invented world",
    "asset":        "asset unavailable -> spec scope constraint + fallback",
    "budget":       "cost estimate -> spec resource input (§5 EXECUTION PLAN / §4b scale-contract)",
    "path-failure": "rescope — the mechanism stands, the offered verification route does not exist",
    "rhetoric":     "wording overstated -> correct the prose; the mechanism was never refuted",
    "needs-review": "mechanical signals are ambiguous — a human must classify this one",
}
REVIVED = {"surrogate", "asset", "budget", "path-failure", "rhetoric"}
_NUM = re.compile(r"[-+]?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?")


def _classify_mechanically(probe_src: str, probe_id: str, evidence: str) -> str:
    """Best-effort static read. Deliberately conservative: anything it cannot
    place lands in needs-review rather than silently upholding a kill."""
    blob = f"{probe_id} {evidence}"
    if re.search(r"budget|wall.?clock|repro.?cost|feasibility|probe_t(otal|imeout)", blob, re.I):
        return "budget"
    if re.search(r"ships no|not published|never published|no such (pairs|data)|dataset .*(missing|absent)",
                 evidence, re.I):
        return "asset"
    if "sympy" in probe_src:
        return "uphold"
    if re.search(r"np\.load|pd\.read_|zipfile|loadtxt|genfromtxt|open\([\"'][^\"']+\.(csv|json|npy|txt)",
                 probe_src):
        return "uphold"
    if re.search(r"default_rng|np\.random", probe_src):
        return "surrogate"
    return "needs-review"


def _obligation(row: dict) -> dict:
    """Turn a premise row into a verification OBLIGATION, stripped of any number
    the dead probe produced. A figure measured inside an invented world reads
    downstream as a measurement; carrying it forward is what poisons the spec."""
    premise = (row.get("premise") or "").strip()
    probe = row.get("probe") or {}
    crit = probe.get("criterion") or {}
    return {
        "premise": premise,
        "status": "deferred",
        "settles_it": crit.get("metric") or "(state the measurement that settles this)",
        "consequence_if_false": row.get("consequence_if_false") or "",
        "discarded_probe": probe.get("id"),
        "note": "Verify-stage number DISCARDED — it came from a self-written model, "
                "not a measurement. Phase-0 must settle this on the real instrument.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", required=True)
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--adjudication", type=Path, default=None,
                    help="JSON {\"<arxiv_id>-<key>\": {\"class\": ..., \"why\": ...}} overriding the scan")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    root = args.data_root or config.data_root()
    ledger_p = root / "data" / "cache" / f"week-{args.week}-ideation-ledger.json"
    bundles = root / "data" / "ideations" / args.week / "bundles"
    if not ledger_p.exists():
        print(f"replay_kills: no ledger at {ledger_p}", file=sys.stderr)
        return 2
    ledger = json.loads(ledger_p.read_text())

    adj = {}
    if args.adjudication and args.adjudication.exists():
        adj = json.loads(args.adjudication.read_text())

    out_dir = args.out or (root / "data" / "ideations" / args.week / "replay")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows, revived = [], []
    for aid, ps in sorted((ledger.get("papers") or {}).items()):
        for key, c in sorted((ps.get("candidates") or {}).items()):
            death = c.get("death")
            cand = f"{aid}-{key}"
            if not death:
                rows.append({"candidate": cand, "original": c.get("status"),
                             "class": "survivor", "disposition": "unchanged", "source": "-"})
                continue
            evidence = death.get("evidence") or ""
            bdir = bundles / cand
            probe_src, probe_ids = "", re.findall(r"\b([PT]\d[\w-]*)", evidence)
            for pid in probe_ids:
                f = bdir / "probes" / pid / "probe.py"
                if f.exists():
                    probe_src += f.read_text(errors="ignore")
            mech = _classify_mechanically(probe_src, " ".join(probe_ids), evidence)
            entry = adj.get(cand)
            klass = (entry or {}).get("class", mech)
            source = "hand" if entry else "scan"
            rows.append({
                "candidate": cand,
                "original_kill_reason": death.get("kill_reason"),
                "original_stage": death.get("stage"),
                "class": klass,
                "mechanical_guess": mech,
                "agrees": mech == klass,
                "source": source,
                "why": (entry or {}).get("why", ""),
                "disposition": DISPOSITIONS.get(klass, "?"),
                "working_title": c.get("working_title"),
            })
            if klass in REVIVED:
                obligations = []
                bj = bdir / "bundle.json"
                if bj.exists():
                    b = json.loads(bj.read_text())
                    for r in ((b.get("premises") or {}).get("rows") or []):
                        if r.get("status") == "probed_fail":
                            obligations.append(_obligation(r))
                revived.append({
                    "candidate": cand,
                    "class": klass,
                    "working_title": c.get("working_title"),
                    "direction_zh": c.get("direction_zh"),
                    "claim": c.get("claim"),
                    "bundle_dir": c.get("bundle_dir"),
                    "carries_forward": DISPOSITIONS.get(klass),
                    "verification_obligations": obligations,
                    "still_owes": ("a rewritten verification route" if klass == "path-failure"
                                   else "Phase-0 kill-or-confirm on the real instrument"),
                })

    (out_dir / "reclassification.json").write_text(
        json.dumps({"week": args.week, "generated_by": "replay_kills.py",
                    "ledger_untouched": str(ledger_p), "rows": rows}, ensure_ascii=False, indent=2))
    (out_dir / "revived.json").write_text(
        json.dumps({"week": args.week, "candidates": revived}, ensure_ascii=False, indent=2))

    kills = [r for r in rows if r.get("original_kill_reason")]
    upheld = [r for r in kills if r["class"] == "uphold"]
    review = [r for r in kills if r["class"] == "needs-review"]
    disagree = [r for r in kills if r["source"] == "hand" and not r["agrees"]]

    md = [f"# {args.week} — kill re-adjudication under the 2026-09 evidence rules", "",
          f"- kills in ledger: **{len(kills)}**",
          f"- upheld: **{len(upheld)}**",
          f"- revived: **{len(revived)}**",
          f"- needs human review: **{len(review)}**",
          f"- hand adjudication disagreed with the static scan on **{len(disagree)}** "
          f"of {sum(1 for r in kills if r['source']=='hand')} — the scan alone is not trustworthy here", "",
          "The ledger was NOT modified.", "",
          "| candidate | original | class | source | disposition |", "|---|---|---|---|---|"]
    for r in kills:
        md.append(f"| `{r['candidate']}` | {r['original_kill_reason']} | **{r['class']}** | "
                  f"{r['source']}{'' if r['agrees'] else ' ≠scan'} | {r['disposition']} |")
    if revived:
        md += ["", "## Revived candidates", ""]
        for v in revived:
            md.append(f"- **`{v['candidate']}`** ({v['class']}) — {v['working_title']}  ")
            md.append(f"  carries forward: {v['carries_forward']}; still owes: {v['still_owes']}")
    (out_dir / "REPLAY.md").write_text("\n".join(md) + "\n")

    print(json.dumps({"week": args.week, "kills": len(kills), "upheld": len(upheld),
                      "revived": len(revived), "needs_review": len(review),
                      "scan_disagreements": len(disagree), "out": str(out_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
