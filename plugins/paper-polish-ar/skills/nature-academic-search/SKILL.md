---
name: nature-academic-search
description: >-
  Multi-source scholarly literature search + citation verification via WebSearch/WebFetch
  (PubMed, CrossRef, arXiv, Semantic Scholar public APIs — no MCP server). Loaded by name as a
  citation capability (config drafting.citation_skills; the /review investigator/experimenter
  hints). Invoke for coordinated multi-step literature workflows — multi-source search sweeps,
  verifying a citation really supports a claim, reference triage/dedup.
user-invocable: true
metadata:
  version: 3.0.0
  author: Community contribution; 2026-07-06 downgraded from MCP tools to WebSearch/WebFetch (dossier-12 H1 — the MCP server was never registered; machinery archived in ../../stale/nature-academic-search-mcp/)
---

# Academic search — WebSearch/WebFetch multi-source guide

**Tooling reality (read first).** There are NO MCP search tools in this environment — the runtime
has never had them (the bundled server was never registered; its code is archived under the plugin's
`stale/nature-academic-search-mcp/`, restorable if someone deliberately wires `.mcp.json` + keys).
Your live tools are **WebSearch** (discovery) and **WebFetch** (structured API pulls + page reads).
Everything below routes through those two. In the auto-research loop, prefer the S2 mechanical probe
(`s2_novelty.py`, see the LITERATURE prompts) BEFORE this skill's web sweeps — it is denser per token.

## Source routing (T1 first; parallel where independent)

| Source | Best for | WebFetch URL pattern |
|---|---|---|
| Semantic Scholar | relevance search, citations graph, TL;DR | `https://api.semanticscholar.org/graph/v1/paper/search?query=<q>&fields=title,year,authors,abstract,externalIds,citationCount` |
| CrossRef | DOI resolution, metadata verification | `https://api.crossref.org/works?query.bibliographic=<title>&rows=5` or `/works/<doi>` |
| arXiv | preprints, CS/math/physics | `http://export.arxiv.org/api/query?search_query=all:<q>&max_results=10` |
| PubMed | biomed; MeSH | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=<q>&retmode=json` then `esummary.fcgi?db=pubmed&id=<ids>&retmode=json` |
| Publisher / Google Scholar | last resort, no API contract | WebSearch, then WebFetch the landing page; warn that results may be incomplete |

Discipline:
1. **Query short.** 3–6 core keywords; long queries silently return junk/empty. Re-query one variant
   before concluding a miss.
2. **Verification is a READ, not a match.** To verify a citation supports a claim: resolve the DOI
   (CrossRef), WebFetch the abstract/full text, and read it against the exact claim — a
   real-but-irrelevant paper is a miscitation.
3. **Never fabricate** a DOI/year/author — skip what you cannot verify, and say so.
4. **Dedup by DOI first**, then normalized title+year (see `references/dedup-engine.md`).

## Method depth (load on demand)

`references/` holds the method playbooks — written in the MCP era; substitute the URL patterns above
wherever they name an MCP tool: `search-strategy.md` (query construction, MeSH),
`source-tiers.md` (T1→T3 reliability routing), `citation-parser.md` + `ris-bibtex-format.md` +
`dedup-engine.md` (citation-file wrangling), `workflows/wf1..wf5` (multi-source search / citation
verification / MeSH strategy / citation-file management / reference management).
