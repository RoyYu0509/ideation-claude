#!/usr/bin/env python3
"""Build data/profile/citation-graph.json from papers.json (citation_mode: graph).

  bash bin/run_py.sh scripts/build_citation_graph.py [--papers P] [--out O] [--alpha A] [--top N] [--if-stale]

arxiv-scout (Phase 1.8) runs it with --if-stale before every prefetch in graph mode: it rebuilds
only when the graph is missing, was built from another papers.json (e.g. after a profile rebuild), or
under an older schema / seed rule.

What it does (lib/citation_graph.py holds the math; this file only does I/O):
  1. seeds   = every CORE profile paper with a Semantic Scholar id (layer 1; lib/channel_spec.graph_seed_papers —
     peripheral papers are excluded, like in every other channel; since 2026-09-17, schema 3);
     layer 2 = their reference_ids (already in papers.json — the ONLY source of seed edges,
     so the sha lock below pins them; a seed whose reference_ids is empty stays a dangling
     seed and is listed in a warning — rebuild papers.json if that is wrong);
  2. ONE S2 batch over seeds + layer 2 → each layer-2 paper's reference list (gives layer 3)
     and every node's citationCount; ONE more batch over layer 3 → citationCount only
     (no third hop);
  3. personalized PageRank restarting at the seeds, weight = ppr * 1/log(1 + citationCount);
  4. writes the graph with the sha256 of the papers.json it was built from. prefetch.py
     (citation_mode: graph) refuses to run if that sha no longer matches — rebuild here.

Prints a hub report (heaviest nodes) so a tool paper dominating the walk is visible at once.
Parameters are fixed a priori (config prefetch.citation_graph_alpha) and never tuned on labels.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import citation_graph as CG  # noqa: E402
from lib import channel_spec as CS  # noqa: E402
from lib import config, s2_client  # noqa: E402

FIELDS_COUNT = ("paperId", "citationCount")


def _log(msg: str) -> None:
    print(f"[build_citation_graph] {msg}", file=sys.stderr, flush=True)


def fetch_layers(seed_refs: dict[str, list[str]]) -> tuple[dict[str, list[str]], dict[str, int | None]]:
    """Returns (refs_by_node for seeds + layer 2, citation_counts for every node in all 3 layers).

    Seed edges come from papers.json ONLY (never back-filled from S2 here): a reference
    added from S2 would carry no citationCount and no layer-3 expansion, i.e. enter the
    walk as a max-weight orphan, and it would not be covered by the papers.json sha lock."""
    refs_by_node: dict[str, list[str]] = {s: list(r) for s, r in seed_refs.items()}
    counts: dict[str, int | None] = {}
    layer2 = sorted({r for refs in seed_refs.values() for r in refs} - set(seed_refs))
    ids = sorted(seed_refs) + layer2
    _log(f"S2 batch 1: {len(ids)} papers (seeds {len(seed_refs)} + layer 2 {len(layer2)}) → references + citationCount")
    refs, extras, st = s2_client.papers_references(ids, extra_fields=("citationCount",))
    for pid, r, ex in zip(ids, refs, extras):
        if r is None:
            continue
        counts[pid] = (ex or {}).get("citationCount")
        if pid in seed_refs:
            continue                                  # seed edges: papers.json is the only source
        refs_by_node[pid] = sorted(r)
    _log(f"  on S2 {st['found']}/{st['n']} · with references {st['with_refs']} · retried {st['retried']} "
         f"(recovered {st['recovered']}) · unresolved (referenceCount > 0, no records) {st['unresolved']}")
    if st["n"] - st["found"]:
        _log(f"  {st['n'] - st['found']} not on S2 (kept as nodes without out-edges)")
    layer3 = sorted({r for pid in layer2 for r in refs_by_node.get(pid, ())} - set(refs_by_node))
    _log(f"S2 batch 2: {len(layer3)} layer-3 papers → citationCount only")
    got3 = s2_client.papers_batch(layer3, fields=FIELDS_COUNT)
    for pid, paper in zip(layer3, got3):
        counts[pid] = paper.get("citationCount") if paper else None
    return refs_by_node, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--papers", type=Path, default=None, help="default: data/profile/papers.json")
    ap.add_argument("--out", type=Path, default=None, help="default: data/profile/citation-graph.json")
    ap.add_argument("--alpha", type=float, default=None, help="default: config prefetch.citation_graph_alpha")
    ap.add_argument("--top", type=int, default=10, help="rows in the hub report")
    ap.add_argument("--if-stale", action="store_true",
                    help="do nothing when <out> already matches papers.json (sha + structure); arxiv-scout "
                         "runs this before every prefetch in citation_mode graph")
    args = ap.parse_args()

    cfg = config.load_config()
    papers_path = args.papers or (config.profile_dir() / "papers.json")
    out = args.out or (config.profile_dir() / "citation-graph.json")
    alpha = args.alpha if args.alpha is not None else cfg.citation_graph_alpha
    if args.if_stale and out.exists():
        try:
            CG.load_graph(out, papers_path)
        except CG.CitationGraphError as e:
            _log(f"{out.name} is stale or invalid — rebuilding ({e})")
        else:
            _log(f"{out.name} matches {papers_path.name} — up to date, not rebuilt")
            print(str(out))
            return 0

    with open(papers_path, encoding="utf-8") as f:
        papers = json.load(f).get("papers", [])
    seed_refs = {p["paper_id"]: [r for r in (p.get("reference_ids") or []) if r]
                 for p in CS.graph_seed_papers(papers)}
    skipped = sum(1 for p in papers if p.get("paper_id") and p.get("peripheral"))
    if not seed_refs:
        _log("ERROR: no profile paper has a Semantic Scholar id — nothing to walk from. For this researcher "
             "set prefetch.citation_mode: coupling (or use_citation_signal: false)")
        return 2
    empty = sorted(s for s, r in seed_refs.items() if not r)
    _log(f"{len(papers)} profile papers, {len(seed_refs)} core with an S2 id, "
         f"{len(seed_refs) - len(empty)} with references; {skipped} peripheral paper(s) not seeded")
    if empty:
        _log(f"WARNING: {len(empty)} seed(s) have no reference_ids in papers.json and stay dangling "
             f"(restart-only) nodes: {empty}. If S2 has their references now, rebuild papers.json first.")

    refs_by_node, counts = fetch_layers(seed_refs)
    doc = CG.build_graph_doc(list(seed_refs), refs_by_node, counts,
                             papers_sha256=CG.sha256_file(papers_path),
                             built_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                             alpha=alpha)
    doc["source"] = {"papers": str(papers_path),
                     "s2": "papers_references(references.paperId, citationCount) for seeds + layer 2; "
                           "papers_batch(citationCount) for layer 3"}
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)

    _log(f"graph: {doc['n_seeds']} seeds · {doc['n_nodes']} nodes · {doc['n_edges']} edges · alpha {alpha}")
    _log(f"hub report (top {args.top} by weight = ppr * 1/log(1+citations)):")
    for r in CG.hub_report(doc, args.top):
        _log(f"  {r['paper_id']}  weight {r['weight']:.3e}  ppr {r['ppr']:.3e}  citations {r['citation_count']}")
    _log(f"wrote {out}")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
