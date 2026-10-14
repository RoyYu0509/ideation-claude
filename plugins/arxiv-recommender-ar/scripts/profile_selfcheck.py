#!/usr/bin/env python3
"""Profile self-check (REC-SYSTEM-V2 B4): does each thread find its own held-out paper? Reports only.

For every ACTIVE thread with >= 2 core members, hold out ONE member (its newest paper with an
abstract — deterministic), drop it from the profile, inject the held-out papers into a dev-week
pool, run the real pool builder (prefetch.run, v2 channels, configured pool rule) and report per
thread: did the held-out paper get a seat, which channel seated it, where its own thread channel
ranked it. Also the seat usage and each phrase's document frequency / hits on the dev pool.

Rules of use:
  * The dev pool must lie OUTSIDE the evaluation sampling frame (e.g. W24, first versions
    2026-06-08..06-14, for the 06-15 frame) — never tune on evaluation weeks.
  * A floor check, not an objective: a researcher's own papers are not the same as what they
    want to read. The agent may fix STRUCTURAL problems it reveals (a thread that finds nothing →
    check its members and phrases; a generic phrase → replace it) but must NOT add words that
    only the held-out paper contains.
  * Hold-outs are stratified by thread: holding out the newest papers overall once emptied a
    whole emerging thread (A1-c).

Usage: bin/run_py.sh scripts/profile_selfcheck.py --pool <dev-week candidates.json> [--no-citation]
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prefetch  # noqa: E402
from lib import config  # noqa: E402
from lib import profile_papers as PP  # noqa: E402
from profile_finalize import phrase_report  # noqa: E402

_EPOCH = date(1900, 1, 1)


def pick_holdouts(profile: dict, papers: list[dict]) -> tuple[dict[str, dict], dict[str, str]]:
    """({thread name: held-out paper}, {thread name: why not held out})."""
    by_key = {PP.paper_key(p): p for p in papers}
    held: dict[str, dict] = {}
    skipped: dict[str, str] = {}
    for t in profile.get("threads") or []:
        name = t.get("name")
        core = [by_key[k] for k in (t.get("papers") or []) if k in by_key and not by_key[k].get("peripheral")]
        with_abs = [p for p in core if p.get("abstract")]
        if t.get("status") != "active":
            skipped[name] = "legacy thread (no seats by design)"
        elif len(core) < 2:
            skipped[name] = "one member only — holding it out would empty the thread"
        elif not with_abs:
            skipped[name] = "no member with an abstract"
        else:
            held[name] = max(with_abs, key=lambda p: (PP.paper_date(p) or date(int(p.get("year") or 1900), 1, 1)
                                                      if p.get("year") or PP.paper_date(p) else _EPOCH,
                                                      PP.paper_key(p)))
    return held, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool", type=Path, required=True, help="dev-week candidates.json OUTSIDE the evaluation frame")
    ap.add_argument("--no-citation", action="store_true")
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args()

    cfg = config.load_config()
    pdir = config.profile_dir()
    profile = json.loads((pdir / "profile.json").read_text(encoding="utf-8"))
    papers = json.loads((pdir / "papers.json").read_text(encoding="utf-8")).get("papers") or []
    if profile.get("schema_version") != 2:
        print("[profile_selfcheck] ERROR: profile.json is not finalized (run scripts/profile_finalize.py first)",
              file=sys.stderr)
        return 1
    cand_data = json.loads(args.pool.read_text(encoding="utf-8"))

    held, skipped = pick_holdouts(profile, papers)
    held_keys = {PP.paper_key(p) for p in held.values()}
    prof = copy.deepcopy(profile)
    for t in prof["threads"]:
        t["papers"] = [k for k in (t.get("papers") or []) if k not in held_keys]
    rest = [p for p in papers if PP.paper_key(p) not in held_keys]
    pool = copy.deepcopy(cand_data)
    held_axids = {p.get("arxiv_id") for p in held.values() if p.get("arxiv_id")}
    pool["candidates"] = [c for c in pool["candidates"] if c.get("arxiv_id") not in held_axids]
    sid = {name: f"selfcheck:{PP.paper_key(p)}" for name, p in held.items()}
    for name, p in held.items():
        pool["candidates"].append({"arxiv_id": sid[name], "title": p.get("title") or "", "abstract": p.get("abstract") or "",
                                   "authors": [], "categories": p.get("categories") or [], "submitted": None})

    graph_off = cfg.use_citation_signal and cfg.citation_mode == "graph" and not args.no_citation
    if graph_off:
        print("[profile_selfcheck] citation_mode graph: the graph was built from the FULL papers.json, held-out "
              "papers included, so it would find them through their own references — citation channel OFF here",
              file=sys.stderr)
    pre, ch = prefetch.run(pool, prof, rest, cfg, top_k=cfg.prefetch_top_k, channel_set="v2",
                           pool_rule=cfg.pool_rule, signals=prefetch.default_signals(cfg, "v2"),
                           use_citation=False if (args.no_citation or graph_off) else None, use_quality=False)
    in_pool = {c["arxiv_id"]: c for c in pre["candidates"]}
    name_to_channel = {label: chan for chan, label in ch["thread_labels"].items()}
    rows = []
    for t in prof["threads"]:
        name = t.get("name")
        if name not in held:
            rows.append({"thread": name, "held_out": None, "note": skipped.get(name)})
            continue
        own = ch["channels"].get(name_to_channel.get(name, ""), [])
        c = in_pool.get(sid[name])
        rows.append({
            "thread": name, "held_out": PP.paper_key(held[name]), "title": held[name].get("title"),
            "in_pool": bool(c), "seated_by": c["seated_by"] if c else None,
            "own_channel_rank": own.index(sid[name]) + 1 if sid[name] in own else None,
            "channel_ranks": c["channel_ranks"] if c else None,
        })
    texts = [f"{c.get('title') or ''}. {c.get('abstract') or ''}" for c in cand_data["candidates"]]
    report = {
        "pool": str(args.pool), "pool_size": len(cand_data["candidates"]), "pool_rule": cfg.pool_rule,
        "signals": pre["signals"], "citation": pre["citation_mode"],
        "n_held_out": len(held), "found": sum(1 for r in rows if r.get("in_pool")),
        "held_out": rows, "seats": pre["seats"], "seated": dict(Counter(c["seated_by"] for c in pre["candidates"])),
        "phrases": phrase_report(prof["threads"], texts),
    }
    rpath = args.report or (pdir / "selfcheck.json")
    rpath.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n| thread | held-out paper | in pool | seated by | rank in own channel |\n|---|---|---|---|---|")
    for r in rows:
        if r["held_out"] is None:
            print(f"| {r['thread']} | — ({r['note']}) | | | |")
        else:
            print(f"| {r['thread']} | {(r['title'] or '')[:60]} | {'yes' if r['in_pool'] else 'NO'} | "
                  f"{r['seated_by'] or ''} | {r['own_channel_rank']} |")
    print(f"\nfound {report['found']}/{report['n_held_out']} · seats {report['seats']} · seated {report['seated']}")
    print("most generic phrases (df% in the dev pool): "
          + ", ".join(f"{p['phrase']} {p['df_pct']}%" for p in report["phrases"][:8]))
    print(f"report: {rpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
