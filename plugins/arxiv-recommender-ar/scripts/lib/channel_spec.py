"""The single source of truth for what every recall channel — and every ablation variant of it — needs
from a profile, and how it selects its inputs (2026-09-16).

Three consumers, ONE definition, so they cannot drift:

  * scripts/profile_finalize.py — the coverage check: can this profile derive every channel × variant?
    A profile that cannot is refused (exit 1, no profile.json written).
  * scripts/prefetch.py — the production channels select their inputs through these same functions.
  * report-v2/ablation/profile_view.py — the ablation runtime iterates VARIANTS and derives each input here
    (it imports this module with the plugin's scripts/ directory on sys.path: `from lib import channel_spec`).

Before this module existed the ablation adapter had its own copy of the selection rules, and within one
afternoon five of them had drifted from production (the prf window, pW's members, b2's matching rule,
what b1 means once the top-level keywords became script-extracted, and the month-end rule of the time
window). Every rule now lives here and nowhere else.

Everything is a pure function over plain dicts: `profile` (profile.json, or the parts being assembled
into it) and `papers` (papers.json["papers"]). No file I/O, no config loading, no encoding — callers load
files and read config, then pass values in. The one thing a pure function cannot see is whether a
companion FILE exists and is valid (citation-graph.json, ref_abstracts.json); callers load those and put
the result into `View.companions`.

A variant that cannot be derived raises `Unavailable`, naming what and where from. Two kinds:
  MISSING  a raw material is absent (no paper_notes, a tool never ran, a companion file is stale) —
           always a finalize error;
  EMPTY    the raw materials are complete but this researcher's data gives the rule nothing to select
           (no phrase shared by two papers, no reference cited twice) — reported, and a finalize error
           only when the variant is one production runs under the current config.
**Nothing here ever falls back to a different variant** — a silent fallback would put a normal-looking
number in an ablation table that measures something else. The ablation runtime refuses an EMPTY arm too.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from . import bm25
from . import profile_papers as PP

# Where a raw material comes from — the three columns of the coverage table.
AGENT = "agent"                # judgement the profile builder writes (paper_notes, threads, recent_direction)
PAPERS = "papers.json"         # the owner-confirmed paper list
COMPANION = "companion"        # files a deterministic tool writes next to profile.json

SCHEMA_V3 = 3

# Constants fixed a priori (EVAL-PLAN 2026-09-14 §3) — never tuned on labels, not config knobs.
REFS_MIN_PAPERS = 2            # a reference enters the refs channel when >= 2 core own papers cite it
B2_MIN_PAPERS = 2              # b2 keeps an agent phrase printed by >= 2 core own papers
NOTE_MAX_KEYWORDS = 5
NOTE_MAX_FIELD_WORDS = 8

YEAR_ONLY_MONTH_DAY = (7, 1)   # a record with only a year is dated mid-year for the prf's time decay
DAYS_PER_MONTH = 365.2425 / 12

# Derivation parameters that live in config (read by the caller, passed in View.params — never defaulted here).
PARAMS = ("prf_half_life_months",)


class Unavailable(RuntimeError):
    """This variant cannot be derived from this profile. Never caught to fall back to another variant."""
    kind = "missing"

    def __init__(self, what: str, source: str):
        super().__init__(what)
        self.what = what
        self.source = source


class Empty(Unavailable):
    """The raw materials are complete, but this researcher's data gives the rule nothing to select."""
    kind = "empty"


class SpecError(ValueError):
    """A caller asked for something the spec does not define (unknown variant, unsupported config value)."""


@dataclass(frozen=True)
class View:
    """Everything the selection rules may look at. Build it once per profile."""
    profile: dict[str, Any]
    papers: list[dict[str, Any]]
    as_of: date
    # companion name → None when present and valid, else the reason it is not usable
    companions: dict[str, str | None] = field(default_factory=dict)
    ref_abstracts: dict[str, dict[str, Any]] | None = None      # S2 paper_id → {title, abstract, ...}
    params: dict[str, Any] = field(default_factory=dict)         # config values the rules need (PARAMS)

    def param(self, name: str) -> Any:
        if name not in self.params:
            raise SpecError(f"View.params lacks {name!r} — build it with params_from_config(cfg)")
        return self.params[name]

    @property
    def core(self) -> list[dict[str, Any]]:
        """Non-peripheral own papers. Every channel uses only these."""
        return [p for p in self.papers if not p.get("peripheral")]

    @property
    def by_key(self) -> dict[str, dict[str, Any]]:
        return {PP.paper_key(p): p for p in self.papers}


def params_from_config(cfg) -> dict[str, Any]:
    """The derivation parameters, read from lib/config.Config — every consumer builds them the same way."""
    return {"prf_half_life_months": cfg.prf_half_life_months}


def view(profile: dict[str, Any], papers: list[dict[str, Any]], *, as_of: date | str | None = None,
         companions: dict[str, str | None] | None = None,
         ref_abstracts: dict[str, dict[str, Any]] | None = None,
         params: dict[str, Any] | None = None) -> View:
    """Build a View. as_of defaults to profile["as_of"]; a profile without one cannot anchor any time window."""
    raw = as_of if as_of is not None else profile.get("as_of")
    if raw is None:
        raise Unavailable("as_of (the profile's recency anchor)", AGENT)
    d = raw if isinstance(raw, date) else date.fromisoformat(str(raw)[:10])
    return View(profile=profile, papers=list(papers), as_of=d, companions=dict(companions or {}),
                ref_abstracts=ref_abstracts, params=dict(params or {}))


# ── shared helpers ────────────────────────────────────────────────────────────

def text_of(p: dict[str, Any]) -> str:
    """The text every semantic channel encodes for a paper — the same string prefetch uses for candidates."""
    return f"{p.get('title') or ''}. {p.get('abstract') or ''}".strip()


def dedup(items) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        k = (x or "").strip()
        if k and k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out


def schema_kind(profile: dict[str, Any]) -> str:
    """'v3' (paper_notes superset) · 'v2prime' (finalized 2026-09-16, extracted keywords, no notes)
    · 'v2' (2026-09-12 and before: the agent wrote the keywords, no finalized_by)."""
    if int(profile.get("schema_version") or 0) >= SCHEMA_V3:
        return "v3"
    return "v2prime" if profile.get("finalized_by") else "v2"


def phrase_hits(phrase: str, texts: list[str]) -> int:
    """How many texts contain the phrase under the production whole-phrase BM25 rule
    (stems, hyphens and a plural s normalized — lib/bm25). The b2 criterion and the notes grounding check."""
    terms = bm25.phrase_terms([phrase])
    if not terms:
        return 0
    return sum(1 for t in texts if terms[0] in set(bm25.tokenize_phrases(t, terms)))


# ── agent parts ───────────────────────────────────────────────────────────────

def notes(v: View) -> list[dict[str, Any]]:
    """paper_notes, one per core paper. Raises unless every core paper has exactly one valid note."""
    raw = v.profile.get("paper_notes") or []
    if not raw:
        raise Unavailable("paper_notes (none in this profile)", AGENT)
    problems = validate_notes(v)
    if problems:
        raise Unavailable(f"paper_notes incomplete — {problems[0]}"
                          + (f" (+{len(problems) - 1} more)" if len(problems) > 1 else ""), AGENT)
    core_keys = {PP.paper_key(p) for p in v.core}
    return [n for n in raw if str(n.get("key")) in core_keys]


def validate_notes(v: View) -> list[str]:
    """Every problem with paper_notes, one line each. Empty list = valid.

    Rules (PROFILE-SCHEMA §2, owner 2026-09-16): one note per core paper, none for a peripheral or unknown
    key; `field` non-empty and at most NOTE_MAX_FIELD_WORDS words; `method` non-empty; 1–NOTE_MAX_KEYWORDS
    keywords, each printed as a whole phrase in the paper's own title + abstract (production BM25 rule).
    """
    by_key = v.by_key
    core_keys = [PP.paper_key(p) for p in v.core]
    out: list[str] = []
    seen: Counter = Counter(str(n.get("key")) for n in v.profile.get("paper_notes") or [])
    for k, c in seen.items():
        if k not in by_key:
            out.append(f"note for unknown paper key {k}")
        elif by_key[k].get("peripheral"):
            out.append(f"note for peripheral paper {k} (peripheral papers get no note)")
        elif c > 1:
            out.append(f"paper {k} has {c} notes (one per paper)")
    missing = [k for k in core_keys if k not in seen]
    if missing:
        out.append(f"{len(missing)} core paper(s) without a note: {missing[:6]}")
    for n in v.profile.get("paper_notes") or []:
        k = str(n.get("key"))
        p = by_key.get(k)
        if p is None or p.get("peripheral"):
            continue
        fld, meth = (n.get("field") or "").strip(), (n.get("method") or "").strip()
        if not fld:
            out.append(f"paper {k}: no field")
        elif len(fld.split()) > NOTE_MAX_FIELD_WORDS:
            out.append(f"paper {k}: field has {len(fld.split())} words (at most {NOTE_MAX_FIELD_WORDS})")
        if not meth:
            out.append(f"paper {k}: no method")
        kws = dedup(n.get("keywords") or [])
        if not 1 <= len(kws) <= NOTE_MAX_KEYWORDS:
            out.append(f"paper {k}: {len(kws)} keywords (1–{NOTE_MAX_KEYWORDS})")
        own = [text_of(p)]
        for kw in kws:
            if not bm25.phrase_terms([kw]):
                out.append(f"paper {k}: keyword '{kw}' has no content words")
            elif phrase_hits(kw, own) == 0:
                out.append(f"paper {k}: keyword '{kw}' is not printed in its title or abstract")
    return out


def threads(v: View) -> list[dict[str, Any]]:
    t = v.profile.get("threads") or []
    if not t:
        raise Unavailable("threads (none in this profile)", AGENT)
    return t


# ── dense ─────────────────────────────────────────────────────────────────────

def d0_text(profile: dict[str, Any]) -> str:
    """recent_direction + every thread summary joined by '. ' ("" when all are empty). prefetch's dense query."""
    parts = [profile.get("recent_direction") or ""] + [t.get("summary") or "" for t in profile.get("threads") or []]
    return ". ".join(p for p in parts if p).strip()


def dense_query(v: View, source: str) -> tuple[list[str], bool]:
    """生产的 dense 通道查询什么:(要编码的文本, 是否先把向量取平均)。

    d0 = 画像的一段话(近期方向 + 各线概括),取最大余弦;
    dN = 每条论文笔记的「field. method」,**向量先平均**再取余弦。两边(生产与消融)都从这里拿规则。
    """
    if source not in DENSE_QUERY_SOURCES:
        raise SpecError(f"prefetch.dense_query = {source!r}; must be one of {sorted(DENSE_QUERY_SOURCES)}")
    return (dense_d0(v), False) if source == "profile_text" else (dense_dN(v), True)


def dense_d0(v: View) -> list[str]:
    """d0: the d0_text of this profile — one query text."""
    text = d0_text(v.profile)
    if not text:
        raise Unavailable("recent_direction / thread summaries (all empty)", AGENT)
    return [text]


def dense_dN(v: View) -> list[str]:
    """dN: one "field. method" text per note; the channel encodes them and averages."""
    return [f"{n.get('field') or ''}. {n.get('method') or ''}".strip() for n in notes(v)]


# ── prf ───────────────────────────────────────────────────────────────────────

def paper_age_months(p: dict[str, Any], as_of: date) -> float:
    """Months from a paper's first version to as_of (>= 0). A year-only record is dated mid-year."""
    d = PP.paper_date(p)
    if d is None and p.get("year"):
        d = date(int(p["year"]), *YEAR_ONLY_MONTH_DAY)
    if d is None:
        raise Unavailable(f"a date for core paper {PP.paper_key(p)} (no first_date and no year)", PAPERS)
    return max(0.0, (as_of - d).days / DAYS_PER_MONTH)


def prf_members(v: View) -> tuple[list[dict[str, Any]], list[float]]:
    """The PRF centroid (owner 2026-09-16, the one pinned design — no prf variants): EVERY core paper with an
    abstract, each weighted 0.5 ** (age in months / prf_half_life_months). The researcher's older work keeps
    a voice; recent work speaks louder; no window ever leaves the centroid empty."""
    have = [p for p in v.core if (p.get("abstract") or "").strip()]
    if not have:
        raise Empty("core papers with an abstract (none)", PAPERS)
    half = float(v.param("prf_half_life_months"))
    if half <= 0:
        raise SpecError(f"prf_half_life_months must be > 0, got {half}")
    return have, [0.5 ** (paper_age_months(p, v.as_of) / half) for p in have]


# ── thread ────────────────────────────────────────────────────────────────────

def thread_members(v: View) -> list[tuple[int, str, list[dict[str, Any]]]]:
    """(1-based thread index, name, member papers that have an abstract) for every thread with at least one.
    A title-only record joins its thread but never feeds a channel (a bare title is not SPECTER2's input)."""
    by_key = v.by_key
    out = []
    for i, t in enumerate(threads(v), 1):
        mem = [by_key[str(k)] for k in t.get("papers") or []
               if str(k) in by_key and not by_key[str(k)].get("peripheral")
               and (by_key[str(k)].get("abstract") or "").strip()]
        if mem:
            out.append((i, t.get("name") or t.get("label") or f"thread_{i}", mem))
    if not out:
        raise Empty("a thread with a member paper that has an abstract (all members are title-only)", PAPERS)
    return out


def thread_members_refs(v: View) -> list[tuple[int, str, list[str]]]:
    """Each thread's member texts ∪ the texts of the members' references that are in the refs corpus
    (cited by >= REFS_MIN_PAPERS core papers, with an S2 abstract). A profile whose papers share no such
    reference just gets the member texts; a ref_abstracts.json that was never built still stops the run."""
    try:
        corpus = {r["paper_id"]: r for r in refs_corpus(v)}
    except Empty:
        corpus = {}
    out = []
    for i, name, mem in thread_members(v):
        rids = sorted({r for p in mem for r in (p.get("reference_ids") or []) if r in corpus})
        out.append((i, name, [text_of(p) for p in mem] + [text_of(corpus[r]) for r in rids]))
    return out


# ── bm25 ──────────────────────────────────────────────────────────────────────

BM25_QUERY_SOURCES = {"extracted": "b4", "agent": "b1",      # config prefetch.bm25_query → variant
                      "agent+extracted": "b3"}              # b3 = 两份词表的并集(生产默认,EVAL-PLAN 修订 #9)
DENSE_QUERY_SOURCES = {"profile_text": "dense:d0",           # config prefetch.dense_query → variant
                       "paper_notes": "dense:dN"}


def agent_phrases(v: View) -> list[str]:
    """b1: phrases the profile AGENT wrote — never the script-extracted list.

    v3       the union of every paper note's keywords
    v2       top-level keywords + every thread's keywords (2026-09-12 and before: the agent wrote both)
    v2prime  unavailable — its top-level keywords are script-extracted (2557f28) and no agent phrases exist;
             using them here would silently turn b1 into b4
    """
    kind = schema_kind(v.profile)
    if kind == "v3":
        return dedup(kw for n in notes(v) for kw in n.get("keywords") or [])
    if kind == "v2":
        got = dedup(list(v.profile.get("keywords") or [])
                    + [kw for t in v.profile.get("threads") or [] for kw in t.get("keywords") or []])
        if not got:
            raise Unavailable("agent-written keywords (none in this v2 profile)", AGENT)
        return got
    raise Unavailable("agent-written keywords (a 2026-09-16 v2 profile stores only script-extracted ones; "
                      "rebuild as v3 to get paper_notes)", AGENT)


def extracted_phrases(v: View) -> list[str]:
    """b4: phrases lib/keyphrases extracted from the own papers at build time (the production BM25 query)."""
    kind = schema_kind(v.profile)
    if kind == "v3" and v.profile.get("keywords_source") != "extracted":
        raise Unavailable("keywords_extracted (the extractor did not run — no weekly pool?)", COMPANION)
    if kind == "v2":
        raise Unavailable("script-extracted keywords (a 2026-09-12 profile's keywords are agent-written)", COMPANION)
    got = dedup(v.profile.get("keywords") or [])
    if not got:
        raise Empty("script-extracted keywords (no phrase is printed by >= 2 own papers)", COMPANION)
    return got


def bm25_phrases(v: View, variant: str) -> list[str]:
    """b1 agent phrases · b2 the ones printed by >= B2_MIN_PAPERS core papers · b3 b1 ∪ b4 · b4 extracted.
    A list whose phrases all normalize to nothing (stop words only) is unavailable, not an empty channel."""
    if variant == "b1":
        got = agent_phrases(v)
    elif variant == "b2":
        texts = [text_of(p) for p in v.core]
        got = [ph for ph in agent_phrases(v) if phrase_hits(ph, texts) >= B2_MIN_PAPERS]
        if not got:
            raise Empty(f"an agent phrase printed by >= {B2_MIN_PAPERS} core papers (none)", AGENT)
    elif variant == "b3":
        got = dedup(agent_phrases(v) + extracted_phrases(v))
    elif variant == "b4":
        got = extracted_phrases(v)
    else:
        raise SpecError(f"unknown bm25 variant {variant!r}")
    if not bm25.phrase_terms(got):
        raise Unavailable(f"{variant} phrases with a content word (all normalize to nothing)",
                          AGENT if variant in ("b1", "b2") else COMPANION)
    return got


# ── category ──────────────────────────────────────────────────────────────────

def category_weights(papers: list[dict[str, Any]]) -> Counter:
    """category → how many CORE own papers carry it (primary or cross-list). EVAL-PLAN §3."""
    w: Counter = Counter()
    for p in papers:
        if p.get("peripheral"):
            continue
        cats = {c for c in (p.get("categories") or []) if c}
        if p.get("primary_category"):
            cats.add(p["primary_category"])
        for c in cats:
            w[c] += 1
    return w


def category(v: View) -> Counter:
    w = category_weights(v.papers)
    if not w:
        raise Empty("arXiv categories on the core papers (none)", PAPERS)
    return w


# ── refs ──────────────────────────────────────────────────────────────────────

def ref_ids(papers: list[dict[str, Any]], min_papers: int = REFS_MIN_PAPERS) -> list[str]:
    """S2 ids cited by >= min_papers core own papers (self-citations kept, EVAL-PLAN §3)."""
    cnt: Counter = Counter()
    for p in papers:
        if not p.get("peripheral"):
            for r in set(p.get("reference_ids") or []):
                cnt[r] += 1
    return sorted(r for r, n in cnt.items() if n >= min_papers)


def refs_corpus(v: View) -> list[dict[str, Any]]:
    """The refs channel's documents: ref_ids with an S2 abstract (ref_abstracts.json)."""
    reason = v.companions.get("ref_abstracts.json", "not loaded")
    if reason is not None or v.ref_abstracts is None:
        raise Unavailable(f"ref_abstracts.json ({reason or 'not loaded'})", COMPANION)
    ids = ref_ids(v.papers)
    if not ids:
        raise Empty(f"references cited by >= {REFS_MIN_PAPERS} core papers (none)", PAPERS)
    out = []
    for r in ids:
        m = v.ref_abstracts.get(r) or {}
        if (m.get("abstract") or "").strip():
            out.append({"paper_id": r, "title": m.get("title") or "", "abstract": m["abstract"]})
    if not out:
        raise Empty(f"an S2 abstract for any of the {len(ids)} references (none)", COMPANION)
    return out


# ── citation ──────────────────────────────────────────────────────────────────

def citation(v: View) -> str:
    reason = v.companions.get("citation-graph.json", "not loaded")
    if reason is not None:
        raise Unavailable(f"citation-graph.json ({reason})", COMPANION)
    return "ok"


CITATION_MODES = ("graph", "coupling")                      # config prefetch.citation_mode → citation:<mode>


def coupling_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The own papers bibliographic coupling compares candidates against: the CORE papers, like every other
    channel. prefetch passes exactly this list to citation_signal.score_coupling."""
    return [p for p in papers if not p.get("peripheral")]


def graph_seed_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The seeds of the citation graph (scripts/build_citation_graph.py): the CORE papers with an S2 id.
    Before 2026-09-17 every paper with an S2 id was a seed, peripheral ones included — on the researcher's
    profile one peripheral LLM paper (via Llama 3 & co.) steered 46 of the graph channel's top 300, 30 of them
    graded 0. lib/citation_graph.SEED_RULE records this rule in every graph file."""
    return [p for p in coupling_papers(papers) if p.get("paper_id")]


def citation_coupling(v: View) -> list[str]:
    """citation:coupling — a candidate scores direct citations of the core papers (their S2 paper_id) plus
    shared references (their reference_ids); the candidates' own references are fetched from S2 at run time,
    as for the graph mode. Raw material: papers.json only, no companion file."""
    ids = sorted({r for p in coupling_papers(v.papers)
                  for r in [p.get("paper_id"), *(p.get("reference_ids") or [])] if r})
    if not ids:
        raise Empty("an S2 paper_id or reference on any core paper (none)", PAPERS)
    return ids


# ── channel families (EVAL-PLAN §3; owner 2026-09-16: refs is semantic, alongside dense / prf / thread) ────────

FAMILIES: dict[str, tuple[str, ...]] = {
    "semantic": ("dense", "prf", "thread", "refs"),        # SPECTER2 similarity to some text of the researcher's
    "lexical": ("bm25",),                                   # whole-phrase BM25
    "citation": ("citation",),                              # citation structure, no text
    "metadata": ("category",),                              # arXiv categories, no text
}


def family_of(channel: str) -> str:
    for fam, chans in FAMILIES.items():
        if channel in chans:
            return fam
    raise SpecError(f"channel {channel!r} belongs to no family")


# ── the variant registry ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Variant:
    channel: str
    name: str
    derive: Callable[[View], Any]
    doc: str
    # True when the variant needs the profile AGENT's judgement (paper_notes / threads / recent_direction), i.e. the
    # expensive LLM step of a profile build. A configuration whose variants are all False runs from papers.json and
    # the deterministic tools alone (the ablation's "no-token" razor, EVAL-PLAN amendment #5).
    agent: bool = False

    @property
    def id(self) -> str:
        return f"{self.channel}:{self.name}"


VARIANTS: tuple[Variant, ...] = (
    Variant("dense", "d0", dense_d0, "recent_direction + thread summaries", agent=True),
    Variant("dense", "dN", dense_dN, "one 'field. method' per paper note", agent=True),
    Variant("prf", "recency", prf_members, "every core paper, weight halves every prf_half_life_months"),
    Variant("thread", "members_refs", thread_members_refs, "members ∪ their references in the refs corpus", agent=True),
    *(Variant("bm25", b, (lambda v, b=b: bm25_phrases(v, b)), d, agent=b != "b4") for b, d in (
        ("b1", "agent-written phrases"), ("b2", f"b1 printed by >= {B2_MIN_PAPERS} core papers"),
        ("b3", "b1 ∪ extracted"), ("b4", "script-extracted phrases"))),
    Variant("category", "weights", category, "core papers' arXiv categories"),
    Variant("refs", "corpus", refs_corpus, f"references cited by >= {REFS_MIN_PAPERS} core papers, with abstracts"),
    Variant("citation", "graph", citation, "citation-graph.json built from this papers.json"),
    Variant("citation", "coupling", citation_coupling, "reference overlap with the core papers (S2 ids from papers.json)"),
)


def channel_defaults(cfg) -> dict[str, str]:
    """每个通道在这份配置下的代表变体 —— 不看开关,只看「开了的话用哪一个」。

    消融的一步邻居(`contrasts.py`)要的就是这个:每个通道都得有一个代表,哪怕生产把它关掉了。
    """
    for key, table in (("bm25_query", BM25_QUERY_SOURCES), ("dense_query", DENSE_QUERY_SOURCES)):
        if getattr(cfg, key) not in table:
            raise SpecError(f"prefetch.{key} = {getattr(cfg, key)!r}; must be one of {sorted(table)}")
    if cfg.citation_mode not in CITATION_MODES:
        raise SpecError(f"prefetch.citation_mode = {cfg.citation_mode!r}; must be one of {list(CITATION_MODES)}")
    return {"dense": DENSE_QUERY_SOURCES[cfg.dense_query], "prf": "prf:recency",
            "thread": "thread:members_refs", "refs": "refs:corpus",
            "bm25": BM25_QUERY_SOURCES[cfg.bm25_query] and f"bm25:{BM25_QUERY_SOURCES[cfg.bm25_query]}",
            "citation": f"citation:{cfg.citation_mode}", "category": "category:weights"}


def production_variants(cfg) -> set[str]:
    """生产真正会跑的那几个变体 —— 代表变体里,开关打开的那些。

    关掉的通道不在集合里,所以画像的覆盖检查也不会要求它的原料(例如关掉引文通道就不要引文图)。
    """
    d = channel_defaults(cfg)
    on = {"dense": cfg.use_dense_channel, "prf": cfg.use_prf, "thread": True, "refs": False,
          "bm25": True, "citation": cfg.use_citation_signal, "category": cfg.use_category_channel}
    return {v for ch, v in d.items() if on[ch]}


def _size(out: Any) -> int:
    if isinstance(out, str):
        return 1
    if isinstance(out, tuple):
        return len(out[0])
    try:
        return len(out)
    except TypeError:
        return 1


def coverage(v: View, production: set[str] | None = None) -> list[dict[str, Any]]:
    """One row per channel × variant: ok / EMPTY / MISSING, naming what and from where.

    `blocking` marks the rows a finalize must refuse: every MISSING row, and an EMPTY row on a variant
    production runs (the production channel could not run)."""
    rows = []
    for var in VARIANTS:
        prod = bool(production and var.id in production)
        row = {"id": var.id, "channel": var.channel, "variant": var.name, "doc": var.doc, "production": prod}
        try:
            row.update(status="ok", ok=True, n=_size(var.derive(v)), missing=None, source=None, blocking=False)
        except Unavailable as e:
            row.update(status=e.kind.upper(), ok=False, n=0, missing=e.what, source=e.source,
                       blocking=e.kind == "missing" or prod)
        rows.append(row)
    return rows


def format_table(rows: list[dict[str, Any]]) -> str:
    """The coverage table as text: channel × variant → usable / what is missing (and where from)."""
    lines = [f"{'channel:variant':<22} {'prod':<4} {'status':<8} detail"]
    for r in rows:
        detail = f"{r['n']} item(s)" if r["ok"] else f"[{r['source']}] {r['missing']}"
        if r.get("blocking"):
            detail += "   ← blocks finalize"
        lines.append(f"{r['id']:<22} {'*' if r['production'] else '':<4} {r['status']:<8} {detail}")
    return "\n".join(lines)
