"""Citation prefetch signal — two modes over ONE Semantic Scholar fetch.

coupling (default)
    A candidate is interesting if it (a) directly cites one of the researcher's papers, or
    (b) shares at least one reference with them — BIBLIOGRAPHIC COUPLING (Kessler, 1963):
    two papers are coupled when their reference lists overlap. This is NOT co-citation
    (Small, 1973), which is the opposite direction — two papers co-cited when a third paper
    cites both. Score = `direct_cites * direct_weight + shared_refs * shared_weight`.

graph
    Personalized PageRank over the researcher's 2-hop reference graph (lib/citation_graph.py),
    each reference discounted by 1/log(1 + citationCount) frozen at build time. A candidate
    scores the weight sum of its references, so a paper that only cites papers TWO steps
    from the researcher still gets a score, and a reference everyone cites (Adam) is damped.
    Needs data/profile/citation-graph.json from scripts/build_citation_graph.py; prefetch
    refuses a graph whose papers.json sha does not match (never a silent degrade).

Both modes read the same thing from S2 — the candidate's reference list — and callers that
want both (the bench's coupling-vs-graph arms) fetch ONCE with `fetch_candidate_refs` and
score twice, so the two arms see the identical S2 snapshot.

Coverage is this signal's binding constraint, not its precision. Two causes, one of them
ours: (1) the S2 batch endpoint caps the nested `references` it returns PER REQUEST — with
the old 500-paper chunks most candidates came back with an EMPTY reference list and scored
0 (the "W31: 36 of 250 = 14.4%" figure once recorded here was largely this, not S2
ingestion); since 2026-09-12 `s2_client.papers_references` fetches in chunks of ≤ 100 and
retries under-delivered papers, and prefetch prints found / with_refs / unresolved. (2) About
a third of papers carry a referenceCount but no reference records on any S2 endpoint — a
data limit we can only report.

Score 0 means the candidate is not in the citation list at all (so it ranks last and
contributes nothing to RRF beyond its other-list ranks).
"""
from __future__ import annotations

from typing import Any

from . import citation_graph, s2_client

Refs = set[str]


def fetch_candidate_refs(candidate_arxiv_ids: list[str], stats: dict | None = None) -> list[Refs | None]:
    """ONE S2 fetch (s2_client.papers_references: chunked + one retry pass). Returns a list
    aligned with the input: the candidate's reference set, or None when S2 has no record (too
    new / not ingested / blank id). `stats`, if given, receives the fetch statistics
    (found / with_refs / retried / recovered / unresolved)."""
    out: list[Refs | None] = [None] * len(candidate_arxiv_ids)
    valid = [(i, axid) for i, axid in enumerate(candidate_arxiv_ids) if axid]
    if not valid:
        if stats is not None:
            stats.update({"n": 0, "found": 0, "with_refs": 0, "retried": 0, "recovered": 0, "unresolved": 0})
        return out
    refs, _, st = s2_client.papers_references([f"ArXiv:{axid}" for _, axid in valid])
    for (i, _), r in zip(valid, refs):
        out[i] = r
    if stats is not None:
        stats.update(st)
    return out


def score_coupling(
    refs_list: list[Refs | None],
    profile_papers: list[dict[str, Any]],
    recent_year_cutoff: int | None = None,
    direct_weight: float = 2.0,
    shared_weight: float = 1.0,
) -> list[tuple[int, float]]:
    """[(candidate_index, score)] sorted by score desc, positive scores only."""
    if recent_year_cutoff is not None:
        recent = [p for p in profile_papers if (p.get("year") or 0) >= recent_year_cutoff]
    else:
        recent = profile_papers
    user_paper_ids = {p["paper_id"] for p in recent if p.get("paper_id")}
    user_refs: set[str] = set()
    for p in recent:
        for r in p.get("reference_ids") or []:
            if r:
                user_refs.add(r)

    scored: list[tuple[int, float]] = []
    for i, refs in enumerate(refs_list):
        if refs is None:
            continue
        direct = len(refs & user_paper_ids)
        shared = len(refs & user_refs)
        score = direct * direct_weight + shared * shared_weight
        if score > 0:
            scored.append((i, score))
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored


def score_graph(refs_list: list[Refs | None], graph_doc: dict[str, Any],
                weights: dict[str, float] | None = None) -> list[tuple[int, float]]:
    """[(candidate_index, score)] sorted by score desc, positive scores only; ties broken by
    index so the order is a pure function of the input. `weights` = citation_graph.weights_of
    (graph_doc), passed in when the caller already has it."""
    weights = citation_graph.weights_of(graph_doc) if weights is None else weights
    scored: list[tuple[int, float]] = []
    for i, refs in enumerate(refs_list):
        if refs is None:
            continue
        score = citation_graph.score_candidate(refs, weights)
        if score > 0:
            scored.append((i, score))
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored


def rank(
    candidate_arxiv_ids: list[str],
    profile_papers: list[dict[str, Any]],
    recent_year_cutoff: int | None = None,
    direct_weight: float = 2.0,
    shared_weight: float = 1.0,
) -> list[tuple[int, float]]:
    """coupling mode, fetch + score (the historical entry point; signature unchanged)."""
    if not candidate_arxiv_ids:
        return []
    refs = fetch_candidate_refs(candidate_arxiv_ids)
    return score_coupling(refs, profile_papers, recent_year_cutoff, direct_weight, shared_weight)


def rank_graph(candidate_arxiv_ids: list[str], graph_doc: dict[str, Any]) -> list[tuple[int, float]]:
    """graph mode, fetch + score."""
    if not candidate_arxiv_ids:
        return []
    return score_graph(fetch_candidate_refs(candidate_arxiv_ids), graph_doc)
