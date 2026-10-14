"""lib/channel_spec — the one definition of what every recall channel × variant needs from a profile.

The finalize coverage check, prefetch and the ablation runtime all read these rules, so these tests pin the
semantics that drifted before the module existed: what b1 means in each schema version, how b2 matches,
the prf's time decay, EMPTY vs MISSING, and that nothing ever falls back to another variant."""
from datetime import date

import pytest

from types import SimpleNamespace

from lib import channel_spec as CS

AS_OF = "2026-06-15"
PARAMS = {"prf_half_life_months": 24}


def _papers():
    return [
        {"key": "a", "title": "Physics-informed neural networks for PDEs", "abstract": "We study PINN solvers.",
         "first_date": "2026-06-15", "year": 2026, "categories": ["math.NA"], "reference_ids": ["R1", "R2"]},
        {"key": "b", "title": "Error bounds", "abstract": "Physics informed neural network error bounds.",
         "first_date": "2024-06-15", "year": 2024, "categories": ["math.NA", "cs.LG"], "reference_ids": ["R1"]},
        {"key": "c", "title": "Old work", "abstract": "Quasicontinuum coupling.", "first_date": None, "year": 2022,
         "categories": ["cond-mat.mtrl-sci"], "reference_ids": []},
        {"key": "d", "title": "Big collaboration", "abstract": "LLM agents.", "first_date": "2026-01-01",
         "year": 2026, "categories": ["cs.CL"], "peripheral": True, "reference_ids": ["R1"]},
    ]


def _notes():
    return [{"key": "a", "field": "PDE solvers", "method": "physics-informed neural networks",
             "keywords": ["physics-informed neural networks"]},
            {"key": "b", "field": "error analysis", "method": "error bounds", "keywords": ["error bounds"]},
            {"key": "c", "field": "multiscale materials", "method": "quasicontinuum coupling",
             "keywords": ["quasicontinuum coupling"]}]


def _v3(**over):
    prof = {"schema_version": 3, "finalized_by": "t", "as_of": AS_OF, "paper_notes": _notes(),
            "threads": [{"name": "PINN", "summary": "s", "papers": ["a", "b"]},
                        {"name": "QC", "summary": "s", "papers": ["c"]}],
            "recent_direction": "r", "keywords": ["neural network"], "keywords_source": "extracted"}
    prof.update(over)
    return prof


def _view(profile, papers=None, **kw):
    kw.setdefault("params", PARAMS)
    return CS.view(profile, papers or _papers(), **kw)


# ── b1 / b4: what each schema version can honestly supply ────────────────────

def test_b1_is_only_ever_the_agents_phrases():
    assert CS.bm25_phrases(_view(_v3()), "b1") == ["physics-informed neural networks", "error bounds",
                                                    "quasicontinuum coupling"]
    legacy = {"schema_version": 2, "as_of": AS_OF, "keywords": ["pinn"],
              "threads": [{"name": "t", "papers": ["a"], "keywords": ["error bounds"]}]}
    assert CS.schema_kind(legacy) == "v2" and CS.bm25_phrases(_view(legacy), "b1") == ["pinn", "error bounds"]
    v2prime = {"schema_version": 2, "finalized_by": "f", "as_of": AS_OF, "keywords": ["neural network"],
               "threads": [{"name": "t", "papers": ["a"], "keywords": []}]}
    with pytest.raises(CS.Unavailable) as e:                 # its keywords are extracted — never passed off as b1
        CS.bm25_phrases(_view(v2prime), "b1")
    assert e.value.kind == "missing" and e.value.source == CS.AGENT


def test_b4_needs_a_real_extraction():
    assert CS.bm25_phrases(_view(_v3()), "b4") == ["neural network"]
    with pytest.raises(CS.Unavailable) as e:
        CS.bm25_phrases(_view(_v3(keywords_source=None)), "b4")
    assert e.value.kind == "missing"
    with pytest.raises(CS.Empty):                            # the extractor ran and found nothing
        CS.bm25_phrases(_view(_v3(keywords=[])), "b4")
    legacy = {"schema_version": 2, "as_of": AS_OF, "keywords": ["pinn"], "threads": []}
    with pytest.raises(CS.Unavailable):                      # a 2026-09-12 profile's keywords are the agent's
        CS.bm25_phrases(_view(legacy), "b4")


def test_b2_uses_the_production_whole_phrase_rule():
    # "physics-informed neural networks" and "Physics informed neural network" are one phrase for BM25
    assert CS.bm25_phrases(_view(_v3()), "b2") == ["physics-informed neural networks"]
    notes = _notes()
    notes[0]["keywords"] = ["PDEs"]
    with pytest.raises(CS.Empty):                            # nothing shared by two papers: data, not a defect
        CS.bm25_phrases(_view(_v3(paper_notes=notes)), "b2")


# ── notes ─────────────────────────────────────────────────────────────────────

def test_notes_validation_names_every_problem():
    notes = _notes() + [{"key": "d", "field": "f", "method": "m", "keywords": ["LLM agents"]}]
    notes[0]["keywords"] = ["neural operators"]
    notes[1]["field"] = "one two three four five six seven eight nine"
    notes[2]["keywords"] = ["a", "b", "c", "d", "e", "f"]
    got = " | ".join(CS.validate_notes(_view(_v3(paper_notes=notes))))
    assert "note for peripheral paper d" in got
    assert "'neural operators' is not printed" in got
    assert "field has 9 words" in got and "6 keywords" in got
    with pytest.raises(CS.Unavailable):                      # invalid notes never feed dN
        CS.dense_dN(_view(_v3(paper_notes=notes)))


def test_dN_needs_a_note_for_every_core_paper():
    assert CS.dense_dN(_view(_v3())) == ["PDE solvers. physics-informed neural networks",
                                         "error analysis. error bounds",
                                         "multiscale materials. quasicontinuum coupling"]
    with pytest.raises(CS.Unavailable, match="without a note"):
        CS.dense_dN(_view(_v3(paper_notes=_notes()[:2])))


# ── prf: every core paper, time-decayed ───────────────────────────────────────

def test_prf_halves_every_half_life_and_never_drops_a_paper():
    members, w = CS.prf_members(_view(_v3()))
    assert [p["key"] for p in members] == ["a", "b", "c"]          # peripheral d left out, old c kept
    assert w[0] == pytest.approx(1.0)                              # published on as_of
    assert w[1] == pytest.approx(0.5, abs=1e-3)                    # 24 months before
    age_c = (date(2026, 6, 15) - date(2022, 7, 1)).days / CS.DAYS_PER_MONTH   # year-only → mid-year
    assert w[2] == pytest.approx(0.5 ** (age_c / 24))


def test_prf_refuses_undated_papers_and_missing_params():
    papers = _papers()
    papers[2]["year"] = None
    with pytest.raises(CS.Unavailable, match="a date for core paper c"):
        CS.prf_members(_view(_v3(), papers))
    with pytest.raises(CS.SpecError, match="prf_half_life_months"):
        CS.prf_members(CS.view(_v3(), _papers()))                  # no silent default half-life


# ── companions, EMPTY vs MISSING, coverage ────────────────────────────────────

def test_thread_texts_are_members_plus_shared_references():
    ok = {"citation-graph.json": None, "ref_abstracts.json": None}
    v = _view(_v3(), companions=ok, ref_abstracts={"R1": {"title": "r", "abstract": "ref"}})
    rows = dict((i, texts) for i, _, texts in CS.thread_members_refs(v))
    assert len(rows[1]) == 3                                       # a, b + R1 (cited by two core papers)
    empty = _view(_v3(), companions=ok, ref_abstracts={"R1": {"title": "r", "abstract": ""}})
    rows = dict((i, texts) for i, _, texts in CS.thread_members_refs(empty))
    assert len(rows[1]) == 2                                       # no shared reference with an abstract: the member texts
    with pytest.raises(CS.Unavailable) as e:
        CS.thread_members_refs(_view(_v3(), companions={"ref_abstracts.json": "not built"}))
    assert e.value.kind == "missing" and e.value.source == CS.COMPANION


def test_coverage_blocks_missing_and_production_empty_only():
    papers = _papers()
    for p in papers:
        p["categories"] = []                                       # category: EMPTY, and production runs it
    notes = _notes()
    notes[0]["keywords"] = ["PDEs"]                                # b2: EMPTY, an ablation-only variant
    v = _view(_v3(paper_notes=notes), papers, companions={"citation-graph.json": None,
                                                          "ref_abstracts.json": "not built"})
    rows = {r["id"]: r for r in CS.coverage(v, CS.production_variants(_cfg(bm25_query="extracted")))}
    assert set(rows) == {x.id for x in CS.VARIANTS}
    assert rows["category:weights"]["status"] == "EMPTY" and rows["category:weights"]["blocking"]
    assert rows["bm25:b2"]["status"] == "EMPTY" and not rows["bm25:b2"]["blocking"]
    assert rows["refs:corpus"]["status"] == "MISSING" and rows["refs:corpus"]["blocking"]
    assert rows["prf:recency"]["ok"] and rows["dense:dN"]["ok"]
    assert "blocks finalize" in CS.format_table(list(rows.values()))


def _cfg(**over):
    """production_variants / channel_defaults 只读配置里的这几项。"""
    base = dict(bm25_query="extracted", citation_mode="graph",
                dense_query="paper_notes", use_dense_channel=True, use_prf=True,
                use_citation_signal=True, use_category_channel=True)
    return SimpleNamespace(**(base | over))


def test_production_variants_follow_every_switch():
    assert CS.production_variants(_cfg()) == {"dense:dN", "prf:recency", "thread:members_refs",
                                              "bm25:b4", "citation:graph", "category:weights"}
    assert "bm25:b1" in CS.production_variants(_cfg(bm25_query="agent"))
    assert "bm25:b3" in CS.production_variants(_cfg(bm25_query="agent+extracted"))
    assert "dense:d0" in CS.production_variants(_cfg(dense_query="profile_text"))
    assert "citation:coupling" in CS.production_variants(_cfg(citation_mode="coupling"))
    # 关掉的通道不进集合 —— 覆盖检查就不会要求它的原料
    off = CS.production_variants(_cfg(use_citation_signal=False, use_prf=False, use_dense_channel=False,
                                      use_category_channel=False))
    assert off == {"thread:members_refs", "bm25:b4"}
    for bad in (dict(bm25_query="both"), dict(dense_query="notes"),
                dict(citation_mode="idf")):
        with pytest.raises(CS.SpecError):
            CS.production_variants(_cfg(**bad))


def test_channel_defaults_cover_every_channel_even_when_switched_off():
    """消融的一步邻居要给每个通道一个代表,哪怕生产把它关掉了(refs 生产从来不开)。"""
    d = CS.channel_defaults(_cfg(use_citation_signal=False, use_prf=False, use_dense_channel=False))
    assert set(d) == {"dense", "prf", "thread", "refs", "bm25", "citation", "category"}
    assert d["refs"] == "refs:corpus" and d["citation"] == "citation:graph" and d["prf"] == "prf:recency"


def test_coupling_uses_core_papers_and_needs_only_papers_json():
    papers = _papers()
    papers[0]["paper_id"] = "Pa"
    papers[3]["paper_id"] = "Pd"                                   # peripheral: never a coupling target
    papers[3]["reference_ids"] = ["R9"]
    got = CS.citation_coupling(_view(_v3(), papers))               # no companion file loaded, still derivable
    assert got == ["Pa", "R1", "R2"]
    assert [p["key"] for p in CS.coupling_papers(papers)] == ["a", "b", "c"]


def test_coupling_is_empty_without_ids_or_references():
    papers = _papers()
    for p in papers:
        p["reference_ids"] = []
    with pytest.raises(CS.Empty) as e:
        CS.citation_coupling(_view(_v3(), papers))
    assert e.value.source == CS.PAPERS


def test_families_partition_the_channels():
    """owner 2026-09-16: refs is a semantic channel, alongside dense / prf / thread."""
    channels = {v.channel for v in CS.VARIANTS}
    listed = [c for chans in CS.FAMILIES.values() for c in chans]
    assert sorted(listed) == sorted(channels)                       # every channel in exactly one family
    assert CS.FAMILIES["semantic"] == ("dense", "prf", "thread", "refs")
    assert CS.family_of("refs") == "semantic" and CS.family_of("citation") == "citation"
    with pytest.raises(CS.SpecError):
        CS.family_of("nope")


def test_the_registry_is_the_one_list_everyone_iterates():
    assert [v.id for v in CS.VARIANTS] == [
        "dense:d0", "dense:dN", "prf:recency", "thread:members_refs",
        "bm25:b1", "bm25:b2", "bm25:b3", "bm25:b4", "category:weights", "refs:corpus",
        "citation:graph", "citation:coupling"]


def test_agent_flag_matches_what_the_agent_parts_actually_feed():
    """A variant is flagged agent iff removing the agent's three parts makes it MISSING with source agent."""
    full = _v3()
    stripped = {k: v for k, v in full.items() if k not in ("paper_notes", "threads", "recent_direction")}
    companions = {"citation-graph.json": None, "ref_abstracts.json": None}
    refs = {"R1": {"title": "t", "abstract": "a"}}
    for var in CS.VARIANTS:
        var.derive(_view(full, companions=companions, ref_abstracts=refs))       # the full profile supplies all
        try:
            var.derive(_view(stripped, companions=companions, ref_abstracts=refs))
            needs = False
        except CS.Unavailable as e:
            needs = e.source == CS.AGENT
        assert var.agent == needs, var.id
    assert {v.id for v in CS.VARIANTS if not v.agent} == {
        "prf:recency", "bm25:b4", "category:weights", "refs:corpus", "citation:graph", "citation:coupling"}
