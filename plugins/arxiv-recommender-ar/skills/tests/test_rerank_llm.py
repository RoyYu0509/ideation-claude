"""lib/rerank_llm — the LLM rerank (A0) + thread-quota final select (G1 → TOP) shared with the ablation.

Pins: the frozen prompt texts (SHA as recorded by the evaluated runs), the blinding, the repair rule, the
dealing, and a full build → answer → collect round trip on a toy profile. No model is called anywhere."""
import json
from pathlib import Path

import pytest

from lib import channel_spec as CS
from lib import rerank_llm as RL

AS_OF = "2026-06-15"
PARAMS = {"prf_half_life_months": 24}


def _papers():
    return [{"key": "a", "title": "Physics-informed neural networks for PDEs", "abstract": "We study PINN solvers.",
             "first_date": "2026-06-15", "year": 2026, "categories": ["math.NA"]},
            {"key": "b", "title": "Error bounds", "abstract": "Physics informed neural network error bounds.",
             "first_date": "2024-06-15", "year": 2024, "categories": ["math.NA", "cs.LG"]},
            {"key": "c", "title": "Old work", "abstract": "Quasicontinuum coupling.", "first_date": None,
             "year": 2022, "categories": ["cond-mat.mtrl-sci"]}]


def _profile():
    return {"schema_version": 3, "finalized_by": "t", "as_of": AS_OF,
            "paper_notes": [{"key": "a", "field": "PDE solvers", "method": "PINN",
                             "keywords": ["physics-informed neural networks"]},
                            {"key": "b", "field": "error analysis", "method": "bounds", "keywords": ["error bounds"]},
                            {"key": "c", "field": "multiscale", "method": "QC", "keywords": ["quasicontinuum coupling"]}],
            "threads": [{"name": "PINN", "summary": "solvers", "papers": ["a", "b"]},
                        {"name": "QC", "summary": "coupling", "papers": ["c"]}],
            "recent_direction": "r", "keywords": ["neural network"], "keywords_source": "extracted"}


def _view():
    return CS.view(_profile(), _papers(), params=PARAMS)


def _cands(n=12):
    return [{"arxiv_id": f"2609.{i:05d}", "title": f"Paper {i}", "abstract": f"Abstract {i}.",
             "categories": ["math.NA"] if i % 2 else ["cs.LG"]} for i in range(n)]


@pytest.fixture
def pdir(tmp_path):
    d = tmp_path / "profile"
    d.mkdir()
    (d / "profile.md").write_text("I work on PINNs.\n", encoding="utf-8")
    return d


# ── frozen prompts (SHA recorded in the ablation's RUN.json / RUN-B.json) ──

def test_prompt_texts_are_the_evaluated_ones():
    assert RL.sha16(RL.PROMPT_A0.format(k=100)) == "6010304c2f3993ad"      # formal-5b RUN.json
    assert RL.sha16(RL.PROMPT_L1) == "d74796105ef8bca3"
    assert RL.sha16(RL.PROMPT_G1) == "6073c459ce7e6773"          # smoke-w24 RUN-B.json
    assert RL.sha16(RL.PROMPT_TOP) == "4bad2d5214932b03" and RL.sha16(RL.PROMPT_G0) == "248359c87c4b3d71"


# ── blinding / repair / dealing (the same rules the ablation tests pin) ──

def test_blind_keeps_presentation_order_but_hides_the_rank():
    ids = [f"26{i:02d}.0001" for i in range(20)]
    to_item, to_arxiv = RL.blind(ids, "P", seed=7)
    assert [to_arxiv[to_item[a]] for a in ids] == ids
    nums = [int(to_item[a].split("-")[1]) for a in ids]
    assert sorted(nums) == list(range(1, 21)) and nums != sorted(nums)
    assert RL.blind(ids, "P", seed=7)[0] == to_item


def test_repair_rule():
    rep = RL.repair(["c", "zz", "c", "a"], ["a", "b", "c", "d"])
    assert rep["order"] == ["c", "a"] and rep["full"] == ["c", "a", "b", "d"]
    assert (rep["n_bad"], rep["n_dupes"], rep["n_missing"]) == (1, 1, 2)
    order_in = [f"p{i}" for i in range(300)]
    assert RL.repair(order_in[:100], order_in, want=100)["repair_rate"] == 0
    assert RL.repair(order_in[:90], order_in, want=100)["repair_rate"] == pytest.approx(0.1)


def test_dealing():
    assert RL.n_groups(10) == 4 and RL.n_groups(8) == 5 and RL.n_groups(40) == 1
    groups = RL.deal([f"p{i}" for i in range(10)], 3)
    assert [len(x) for x in groups] == [4, 3, 3] and groups[0] == ["p0", "p3", "p6", "p9"]


def test_prompt_body_excludes_only_the_output_rule(pdir):
    v = _view()
    c = _cands(3)
    items = ["P-0002", "P-0001", "P-0003"]
    p1 = RL.compose_prompt("head", v, pdir, c, items, Path("/x/RESULT.txt"), "shape.")
    p2 = RL.compose_prompt("head", v, pdir, c, items, Path("/y/RESULT.txt"), "shape.")
    assert p1 != p2 and RL.body_sha(p1) == RL.body_sha(p2)
    assert "### Thread 1: PINN" in p1 and "Keywords: physics-informed neural networks, error bounds" in p1
    assert "Authors" not in p1 and "rrf" not in p1.lower()


# ── the production round trip: build → (fake agent) → collect, A0 → G1 → TOP ──

def _answer(unit: dict, lines: list[str]) -> None:
    Path(unit["expects"]).write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_round_trip_a0_g1_top(tmp_path, pdir):
    st = RL.Stage(tmp_path / "wk", "2026-W37", _view(), pdir, _cands(12))
    key = st.key(seed=1)["to_item"]
    a0 = st.build_a0(k=8)
    assert a0["done"] is False and a0["want"] == 8 and Path(a0["spawn"]).exists()
    assert "Read exactly ONE file" in Path(a0["spawn"]).read_text()
    _answer(a0, [key[c["arxiv_id"]] for c in _cands(12)[:8]][::-1])          # reversed top 8
    s = st.collect_a0()
    assert s["n_given"] == 8 and s["repair_rate"] == 0
    assert st.order100() == [c["arxiv_id"] for c in _cands(12)[:8]][::-1]
    assert st.build_a0(k=8)["done"] is True                                    # resume: nothing rebuilt

    g1 = st.build_g1(promote_target=4)                                        # 2 threads → 2 groups
    assert g1["n_groups"] == 2 and g1["group_sizes"] == [4, 4]
    plan = json.loads((tmp_path / "wk" / "G1.plan.json").read_text())
    g0, g1u = g1["units"]
    _answer(g0, [f"PINN\t{key[plan['groups'][0][1]]}", f"QC\t{key[plan['groups'][0][0]]}",
                 f"PINN\t{key[plan['groups'][0][2]]}"])                        # 2nd PINN pick ignored
    _answer(g1u, [f"QC\t{key[plan['groups'][1][3]]}", "Nope\tP-0001"])         # unknown thread ignored
    out = st.collect_g1()
    assert out["n_promoted"] == 3
    prom = json.loads((tmp_path / "wk" / "G1.out.json").read_text())
    assert prom["promoted"] == [a for a in st.order100() if a in set(prom["thread_of"])]

    top = st.build_top(k=5)
    assert top["n_promoted"] == 3 and top["want"] == 3
    _answer(top, [key[prom["promoted"][2]], key[prom["promoted"][0]]])        # gives 2 of 3
    with pytest.raises(SystemExit):                                            # 1/3 short → repair 33% > 5%
        st.collect_top(k=5)
    _answer(top, [key[prom["promoted"][2]], key[prom["promoted"][0]], key[prom["promoted"][1]]])
    fin = st.collect_top(k=5)
    assert fin["n_from_top"] == 3 and fin["n_padded"] == 2 and fin["n_top"] == 5
    f = json.loads(Path(fin["final_path"]).read_text())
    assert [t["arxiv_id"] for t in f["top"][:3]] == [prom["promoted"][2], prom["promoted"][0], prom["promoted"][1]]
    assert all(t["thread"] in ("PINN", "QC") for t in f["top"][:3])
    assert all(t["source"] == "pad" and t["thread"] is None for t in f["top"][3:])
    assert len(f["rest"]) == 12 - 5 and set(f["rest"]) | {t["arxiv_id"] for t in f["top"]} == {c["arxiv_id"] for c in _cands(12)}
    assert f["prompts"]["A0"] == "6010304c2f3993ad"


def test_pass_through_feeds_g1_the_fused_order_without_a_call(tmp_path, pdir):
    """scout.rerank_pass = none (修订 #12): A0's slot holds the recall order; G1 deals it; nothing was asked of a model."""
    st = RL.Stage(tmp_path / "wk", "2026-W37", _view(), pdir, _cands(12))
    r0 = st.pass_through(k=8)
    assert r0["done"] is True and r0["pass"] == "none" and r0["n_given"] == 8
    assert st.order100() == [c["arxiv_id"] for c in _cands(12)[:8]]
    assert not (tmp_path / "wk" / "A0").exists()                              # no unit dir, no prompt
    g1 = st.build_g1(promote_target=4)
    assert g1["n_groups"] == 2 and sum(g1["group_sizes"]) == 8
    assert st.pass_through(k=8)["done"] is True                                # idempotent on resume
