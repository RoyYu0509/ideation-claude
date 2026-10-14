"""Citation-graph channel: personalized PageRank over the researcher's 2-hop reference graph.

Pure functions only (no I/O except the two file helpers at the bottom, which are thin).

The graph
    layer 1  the researcher's own papers (seeds)
    layer 2  every paper they reference
    layer 3  every paper a layer-2 paper references
Edges u -> v mean "u's reference list contains v". A reference list is fixed at submission
time, so the graph never carries information from after the seed papers were written.

The walk (Gori & Pucci 2006 "PaperRank"; Küçüktunç et al. 2012 DaRWR with the backward
direction only) is personalized PageRank restarting uniformly at the seeds; dangling
layer-3 nodes hand their mass back to the restart vector (networkx's default when a
personalization vector is given, so `dangling` is deliberately NOT passed).

Hub discount (Adamic/Adar 1/log form — CiteSeer's CC-IDF idea; the form Inciteful ships):
    w(r) = 1 / log(1 + max(c_r, 1)),  c_r = Semantic Scholar citationCount FROZEN at build time.
The 1/log form is deliberate: 1/c (Resource Allocation) over-concentrates the score on a
handful of rarely-cited references (measured 56% top-10 share on the researcher's pool),
while an in-pool IDF depends on the pool size and cannot be reproduced between a 200-paper
benchmark week and a 2,500-paper production week. Owner decision 2026-09-12.

A candidate scores  sum over its references r of  ppr(r) * w(r).  No reference-list-length
normalization (kept as one change; recorded as a known limitation).

All parameters are fixed a priori and are never tuned on evaluation labels.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 3                        # 3: seeds = core papers only (SEED_RULE); 2: out_edges + versions
SEED_RULE = "core"                        # lib/channel_spec.graph_seed_papers — peripheral papers are never seeds
ALPHA_DEFAULT = 0.85                      # PageRank convention (theadvisor used 0.9) — fixed, not tuned
DISCOUNT = "inv_log1p_citation_count"     # w = 1/log(1 + max(c, 1)); the only discount this module knows
PPR_TOL = 1e-10                           # networkx stops when total change < len(G) * tol
PPR_MAX_ITER = 500


class CitationGraphError(ValueError):
    """The graph file is missing, malformed, or was built from a different papers.json."""


# ── pure graph math ───────────────────────────────────────────────────────────

def build_edges(seed_ids: Iterable[str], refs_by_node: dict[str, Iterable[str]]
                ) -> tuple[list[str], list[tuple[str, str]]]:
    """Nodes = seeds ∪ every id that appears as a key or a reference; edges u→v for each
    reference v of u. Sorted + deduplicated, self-loops dropped, so the result is a pure
    function of its input (the PageRank below is then bit-reproducible)."""
    nodes: set[str] = {s for s in seed_ids if s}
    edges: set[tuple[str, str]] = set()
    for u, refs in refs_by_node.items():
        if not u:
            continue
        nodes.add(u)
        for v in refs or ():
            if v and v != u:
                nodes.add(v)
                edges.add((u, v))
    return sorted(nodes), sorted(edges)


def personalized_pagerank(nodes: Iterable[str], edges: Iterable[tuple[str, str]], seeds: Iterable[str],
                          alpha: float = ALPHA_DEFAULT) -> dict[str, float]:
    """PPR with restart uniform over `seeds`. Dangling nodes (layer 3 has no out-edges)
    fall back to the personalization vector — networkx's default — which is exactly the
    restart we want, so `dangling` is not passed."""
    import networkx as nx  # imported here so the pure helpers above stay import-light

    if not 0.0 < alpha < 1.0:
        raise CitationGraphError(f"alpha must be in (0, 1), got {alpha}")
    node_list = sorted(set(nodes))
    seed_set = {s for s in seeds if s}
    missing = seed_set - set(node_list)
    if missing:
        raise CitationGraphError(f"{len(missing)} seed(s) are not graph nodes: {sorted(missing)[:3]}")
    if not seed_set:
        raise CitationGraphError("no seeds: the researcher has no paper with a Semantic Scholar id")
    g = nx.DiGraph()
    g.add_nodes_from(node_list)
    g.add_edges_from(sorted(set(edges)))
    personalization = {n: (1.0 if n in seed_set else 0.0) for n in node_list}
    try:
        return nx.pagerank(g, alpha=alpha, personalization=personalization, tol=PPR_TOL, max_iter=PPR_MAX_ITER)
    except nx.PowerIterationFailedConvergence as e:
        raise CitationGraphError(f"personalized PageRank did not converge in {PPR_MAX_ITER} iterations "
                                 f"({len(node_list)} nodes, alpha {alpha}): {e}") from e


def discount(citation_count: int | float | None) -> float:
    """w = 1/log(1 + max(c, 1)). Missing / zero counts clamp to 1 so the weight is finite
    (1/ln 2 ≈ 1.44 is the ceiling; Adam's ~1.7e5 citations give ≈ 0.083)."""
    c = 1.0 if citation_count is None else max(float(citation_count), 1.0)
    return 1.0 / math.log1p(c)


def node_weights(ppr: dict[str, float], citation_counts: dict[str, int | None]) -> dict[str, float]:
    """The per-reference weight a candidate collects: ppr(r) * w(r)."""
    return {n: p * discount(citation_counts.get(n)) for n, p in ppr.items()}


def score_candidate(refs: Iterable[str], weights: dict[str, float]) -> float:
    return sum(weights.get(r, 0.0) for r in set(refs))


def concentration(refs_list: Iterable[Iterable[str] | None], weights: dict[str, float], top: int = 10
                  ) -> dict[str, Any]:
    """Mechanical hub diagnostic: what share of ALL score mass across the candidates comes
    from the `top` most-contributing references. (36–37% with the discount on the researcher's
    pool; 56% with 1/c.) Reported, never optimized."""
    mass: dict[str, float] = defaultdict(float)
    for refs in refs_list:
        for r in set(refs or ()):
            w = weights.get(r)
            if w:
                mass[r] += w
    total = sum(mass.values())
    ranked = sorted(mass.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    return {"total": total, "top_share": (sum(v for _, v in ranked) / total) if total else 0.0,
            "top": [{"paper_id": k, "mass": v} for k, v in ranked]}


# ── the graph document ────────────────────────────────────────────────────────

def sha256_file(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _versions() -> dict[str, str]:
    import networkx, scipy  # noqa: PLC0415
    return {"networkx": networkx.__version__, "scipy": scipy.__version__}


def build_graph_doc(seed_ids: Iterable[str], refs_by_node: dict[str, Iterable[str]],
                    citation_counts: dict[str, int | None], papers_sha256: str, built_utc: str,
                    alpha: float = ALPHA_DEFAULT) -> dict[str, Any]:
    """Everything prefetch needs, plus what an audit needs to re-derive it: the two raw
    columns (ppr, citation_count) per node and the full edge list (`out_edges`, keyed by
    source node — layer-3 nodes never appear as keys). `weight` is the product actually
    used at scoring time. `versions` is informational (the walk is scipy power iteration;
    a different networkx/scipy could differ in the last bits)."""
    nodes, edges = build_edges(seed_ids, refs_by_node)
    seeds = sorted({s for s in seed_ids if s})
    ppr = personalized_pagerank(nodes, edges, seeds, alpha=alpha)
    weights = node_weights(ppr, citation_counts)
    out_edges: dict[str, list[str]] = defaultdict(list)
    for u, v in edges:                       # edges are sorted, so each list is sorted
        out_edges[u].append(v)
    return {
        "schema_version": SCHEMA_VERSION,
        "seed_rule": SEED_RULE,
        "papers_sha256": papers_sha256,
        "built_utc": built_utc,
        "alpha": alpha,
        "discount": DISCOUNT,
        "versions": _versions(),
        "n_seeds": len(seeds),
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "n_seeds_without_refs": sum(1 for s in seeds if not out_edges.get(s)),
        "seeds": seeds,
        "out_edges": dict(out_edges),
        "nodes": {n: {"ppr": ppr[n], "citation_count": citation_counts.get(n), "weight": weights[n]}
                  for n in nodes},
    }


def weights_of(doc: dict[str, Any]) -> dict[str, float]:
    return {n: float(v["weight"]) for n, v in doc["nodes"].items()}


def hub_report(doc: dict[str, Any], top: int = 10) -> list[dict[str, Any]]:
    """The `top` heaviest nodes by weight, with their raw ppr / citation_count."""
    rows = [{"paper_id": n, **v} for n, v in doc["nodes"].items()]
    rows.sort(key=lambda r: (-r["weight"], r["paper_id"]))
    return rows[:top]


def check_graph(doc: dict[str, Any], papers_path: Path | str) -> None:
    """Refuse a graph built from a different papers.json, another schema, or with a broken
    node table. Hard error: a stale or corrupt graph must never degrade silently into
    'no citation channel' (scoring never sees a graph that did not pass here)."""
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise CitationGraphError(f"citation graph schema_version {doc.get('schema_version')!r} "
                                 f"!= {SCHEMA_VERSION}; rebuild with scripts/build_citation_graph.py")
    if doc.get("seed_rule") != SEED_RULE:
        raise CitationGraphError(f"citation graph seed_rule {doc.get('seed_rule')!r} != {SEED_RULE!r}; "
                                 "rebuild with scripts/build_citation_graph.py")
    if doc.get("discount") != DISCOUNT:
        raise CitationGraphError(f"citation graph discount {doc.get('discount')!r} != {DISCOUNT!r}")
    want = sha256_file(papers_path)
    if doc.get("papers_sha256") != want:
        raise CitationGraphError(
            f"citation graph was built from a different papers.json "
            f"(graph {str(doc.get('papers_sha256'))[:12]}… vs current {want[:12]}…); "
            f"rebuild with scripts/build_citation_graph.py before using citation_mode=graph")
    nodes = doc.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        raise CitationGraphError("citation graph has no `nodes` table; rebuild with scripts/build_citation_graph.py")
    bad = next((n for n, v in nodes.items()
                if not isinstance(v, dict) or not isinstance(v.get("weight"), (int, float))
                or not isinstance(v.get("ppr"), (int, float)) or v["weight"] < 0 or v["ppr"] < 0), None)
    if bad is not None:
        raise CitationGraphError(f"citation graph node {bad!r} lacks a numeric ppr/weight; rebuild the graph")
    seeds = doc.get("seeds") or []
    if not seeds or any(s not in nodes for s in seeds):
        raise CitationGraphError("citation graph seeds are missing from its node table; rebuild the graph")
    out_edges = doc.get("out_edges")
    if not isinstance(out_edges, dict) or sum(len(v) for v in out_edges.values()) != doc.get("n_edges"):
        raise CitationGraphError("citation graph `out_edges` does not match n_edges; rebuild the graph")


def load_graph(graph_path: Path | str, papers_path: Path | str) -> dict[str, Any]:
    graph_path = Path(graph_path)
    if not graph_path.exists():
        raise CitationGraphError(f"citation graph not found at {graph_path}; "
                                 f"run scripts/build_citation_graph.py after building papers.json")
    with open(graph_path, encoding="utf-8") as f:
        doc = json.load(f)
    check_graph(doc, papers_path)
    return doc
