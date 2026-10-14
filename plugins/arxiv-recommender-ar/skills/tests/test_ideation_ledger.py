"""Unit tests for the deterministic ideation state-machine driver (ideation_ledger.py).

These pin the promote/kill/bounce/converge transitions the driver takes OFF the LLM's plate —
the logic a hand-enacting orchestrator previously approximated from memory (unbounded verify
spins, mis-tracked rounds). Knobs and V0 are monkeypatched so the tests are independent of
config.yaml and of any real bundle on disk.
"""
import json
import types

import pytest

import ideation_ledger as IL


@pytest.fixture(autouse=True)
def fixed_knobs(monkeypatch):
    monkeypatch.setattr(IL, "_knobs", lambda: {
        "rounds_max": 3, "candidates_per_round": 3, "verify_fanout": 1, "survivor_target": 1})


def _args(**kw):
    base = dict(round=1, stage=None, result=None, gated_pool=None, ledger=None, bounce=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


def _run(cmd, led, week, **kw):
    return IL.DISPATCH[cmd](led, week, _args(**kw))


def test_init_idempotent_preserves_progress(tmp_path):
    led = tmp_path / "ledger.json"
    gp = tmp_path / "gp.json"
    gp.write_text(json.dumps([{"arxiv_id": "a"}, {"arxiv_id": "b"}]))
    _run("init", led, "W", gated_pool=str(gp))
    # simulate progress, then re-init: it must NOT clobber the converged paper
    data = json.loads(led.read_text())
    data["papers"]["a"]["status"] = "converged"
    led.write_text(json.dumps(data))
    r = _run("init", led, "W", gated_pool=str(gp))
    assert r["papers"] == 2
    assert json.loads(led.read_text())["papers"]["a"]["status"] == "converged"


def test_apply_generate_registers_and_exhausts(tmp_path):
    led = tmp_path / "ledger.json"
    gp = tmp_path / "gp.json"
    gp.write_text(json.dumps([{"arxiv_id": "a"}, {"arxiv_id": "b"}]))
    _run("init", led, "W", gated_pool=str(gp))
    ideas = tmp_path / "a.json"
    ideas.write_text(json.dumps({"ideas": [{"working_title": "T0", "claim": "C0"},
                                           {"working_title": "T1", "claim": "C1"}]}))
    res = tmp_path / "gen.json"
    res.write_text(json.dumps([
        {"arxiv_id": "a", "has_new_directions": True, "candidate_count": 2, "output_path": str(ideas)},
        {"arxiv_id": "b", "has_new_directions": False, "candidate_count": 0, "exhaustion_note_zh": "无"},
    ]))
    _run("apply-generate", led, "W", result=str(res))
    d = json.loads(led.read_text())["papers"]
    assert set(d["a"]["candidates"]) == {"c0", "c1"}
    assert d["a"]["candidates"]["c0"]["status"] == "generated"
    assert d["a"]["candidates"]["c0"]["claim"] == "C0"
    assert d["b"]["status"] == "exhausted_honest"


def _seed_two_generated(tmp_path):
    """Ledger with paper 'a' holding two generated candidates c0,c1."""
    led = tmp_path / "ledger.json"
    gp = tmp_path / "gp.json"; gp.write_text(json.dumps([{"arxiv_id": "a"}]))
    _run("init", led, "W", gated_pool=str(gp))
    ideas = tmp_path / "a.json"
    ideas.write_text(json.dumps({"ideas": [{"working_title": "T0", "claim": "C0"},
                                           {"working_title": "T1", "claim": "C1"}]}))
    res = tmp_path / "gen.json"
    res.write_text(json.dumps([{"arxiv_id": "a", "has_new_directions": True,
                                "candidate_count": 2, "output_path": str(ideas)}]))
    _run("apply-generate", led, "W", result=str(res))
    return led


def test_apply_screen_kill_and_rank(tmp_path):
    led = _seed_two_generated(tmp_path)
    res = tmp_path / "screen.json"
    res.write_text(json.dumps([{"arxiv_id": "a", "round": 1, "results": [
        {"key": "c0", "verdict": "pass", "rank": 1, "direction": "d0", "direction_zh": "方向0"},
        {"key": "c1", "verdict": "kill", "kill_reason": "scooped", "kill_evidence": "prior X",
         "direction": "d1", "direction_zh": "方向1"},
    ]}]))
    _run("apply-screen", led, "W", result=str(res))
    d = json.loads(led.read_text())["papers"]["a"]
    assert d["candidates"]["c0"]["status"] == "screened" and d["candidates"]["c0"]["rank"] == 1
    assert d["candidates"]["c1"]["status"] == "killed"
    assert len(d["graveyard"]) == 1 and d["graveyard"][0]["kill_reason"] == "scooped"


def test_worklist_verify_promotes_top_fanout_rest_dormant(tmp_path):
    led = _seed_two_generated(tmp_path)
    res = tmp_path / "screen.json"
    res.write_text(json.dumps([{"arxiv_id": "a", "round": 1, "results": [
        {"key": "c0", "verdict": "pass", "rank": 2, "direction": "d0", "direction_zh": "z0"},
        {"key": "c1", "verdict": "pass", "rank": 1, "direction": "d1", "direction_zh": "z1"},
    ]}]))
    _run("apply-screen", led, "W", result=str(res))
    wl = _run("worklist", led, "W", round=1, stage="verify")
    # verify_fanout=1 → only rank-1 (c1) promoted to verify; c0 goes dormant.
    assert [it["key"] for it in wl["items"]] == ["c1"]
    d = json.loads(led.read_text())["papers"]["a"]
    assert d["candidates"]["c1"]["status"] == "verifying"
    assert d["candidates"]["c0"]["status"] == "dormant"


def test_apply_verify_kill_and_v0_pass(tmp_path, monkeypatch):
    led = _seed_two_generated(tmp_path)
    # promote c0 to verifying via a screen+worklist
    res = tmp_path / "s.json"
    res.write_text(json.dumps([{"arxiv_id": "a", "results": [
        {"key": "c0", "verdict": "pass", "rank": 1, "direction": "d", "direction_zh": "z"}]}]))
    _run("apply-screen", led, "W", result=str(res))
    _run("worklist", led, "W", round=1, stage="verify")
    # V0 forced to pass → verified
    monkeypatch.setattr(IL, "_run_v0", lambda c, rnd: {"all_pass": True, "kind": None,
                                                       "failures": [], "out_path": "/x/rc.json"})
    vres = tmp_path / "v.json"
    vres.write_text(json.dumps([{"arxiv_id": "a", "key": "c0", "verdict": "pass",
                                 "bundle_dir": str(tmp_path / "bd"), "claim": "C", "claim_type": "empirical"}]))
    out = _run("apply-verify", led, "W", round=1, result=str(vres))
    assert out["verified"] == ["a:c0"]
    assert json.loads(led.read_text())["papers"]["a"]["candidates"]["c0"]["status"] == "verified"


def test_apply_verify_v0_mechanical_bounces_once_then_kills(tmp_path, monkeypatch):
    led = _seed_two_generated(tmp_path)
    res = tmp_path / "s.json"
    res.write_text(json.dumps([{"arxiv_id": "a", "results": [
        {"key": "c0", "verdict": "pass", "rank": 1, "direction": "d", "direction_zh": "z"}]}]))
    _run("apply-screen", led, "W", result=str(res))
    _run("worklist", led, "W", round=1, stage="verify")
    monkeypatch.setattr(IL, "_run_v0", lambda c, rnd: {"all_pass": False, "kind": "mechanical",
                        "failures": [{"code": "schema", "msg": "bad"}], "out_path": "/x/rc.json"})
    v = tmp_path / "v.json"
    v.write_text(json.dumps([{"arxiv_id": "a", "key": "c0", "verdict": "pass",
                              "bundle_dir": str(tmp_path / "bd"), "claim": "C", "claim_type": "empirical"}]))
    (tmp_path / "bd").mkdir()
    (tmp_path / "bd" / "bundle.json").write_text("{}")
    out1 = _run("apply-verify", led, "W", round=1, result=str(v))
    assert out1["bounce_count"] == 1 and out1["verified"] == [] and out1["killed"] == []
    # post-bounce pass: still failing → KILL (no second bounce)
    out2 = _run("apply-verify", led, "W", round=1, result=str(v), bounce=True)
    assert out2["killed"] == ["a:c0"]
    assert json.loads(led.read_text())["papers"]["a"]["candidates"]["c0"]["status"] == "killed"


def _seed_verified(tmp_path):
    led = _seed_two_generated(tmp_path)
    d = json.loads(led.read_text())
    c = d["papers"]["a"]["candidates"]["c0"]
    c["status"] = "verified"; c["bundle_dir"] = "/x"; c["claim"] = "C"; c["claim_type"] = "empirical"
    led.write_text(json.dumps(d))
    return led


def test_apply_recheck_converges_only_with_significance_confrontation(tmp_path):
    led = _seed_verified(tmp_path)
    res = tmp_path / "rc.json"
    res.write_text(json.dumps([{"arxiv_id": "a", "key": "c0",
        "recheck": {"verdict": "pass", "all_artifacts_reconfirmed": True, "significance": "paper_worthy",
                    "significance_confrontation": {"strongest_rival_row": "FireQ", "why_clears_or_fails": "ok"},
                    "artifact_pass": {"prior_art": True, "premise_probe": True,
                                      "derivation_check": True, "asset_check": True}},
        "refute": {"verdict": "clear"}}]))
    out = _run("apply-recheck", led, "W", round=1, result=str(res))
    assert out["converged"] == ["a:c0"]
    # survivor_target=1 → paper settles to converged
    assert json.loads(led.read_text())["papers"]["a"]["status"] == "converged"


def test_apply_recheck_kills_borderline_without_confrontation(tmp_path):
    led = _seed_verified(tmp_path)
    res = tmp_path / "rc.json"
    res.write_text(json.dumps([{"arxiv_id": "a", "key": "c0",
        "recheck": {"verdict": "pass", "all_artifacts_reconfirmed": True, "significance": "borderline",
                    "significance_confrontation": None},
        "refute": {"verdict": "clear"}}]))
    out = _run("apply-recheck", led, "W", round=1, result=str(res))
    assert out["killed"] == ["a:c0"] and out["converged"] == []
    d = json.loads(led.read_text())["papers"]["a"]
    assert d["candidates"]["c0"]["status"] == "killed"
    assert d["graveyard"][0]["kill_reason"] == "insignificant"


def test_apply_recheck_scooped_by_refute(tmp_path):
    led = _seed_verified(tmp_path)
    res = tmp_path / "rc.json"
    res.write_text(json.dumps([{"arxiv_id": "a", "key": "c0",
        "recheck": {"verdict": "pass", "all_artifacts_reconfirmed": True, "significance": "paper_worthy",
                    "significance_confrontation": {"strongest_rival_row": "R"}},
        "refute": {"verdict": "scooped", "killing_hit": {"title": "T", "why": "does it", "url": "u"}}}]))
    out = _run("apply-recheck", led, "W", round=1, result=str(res))
    assert out["killed"] == ["a:c0"]
    assert json.loads(led.read_text())["papers"]["a"]["graveyard"][0]["kill_reason"] == "scooped"


def test_apply_recheck_prefers_on_disk_verdict_over_passed(tmp_path):
    # L4 anti-fabrication: bundle_dir holds recheck-semantic.json saying BORDERLINE (kill),
    # but the orchestrator passes a fabricated paper_worthy+confrontation verdict. The driver
    # must read the FILE and KILL — a fabricated return cannot force convergence.
    led = _seed_two_generated(tmp_path)
    bd = tmp_path / "bd"; bd.mkdir()
    d = json.loads(led.read_text())
    c = d["papers"]["a"]["candidates"]["c0"]
    c["status"] = "verified"; c["bundle_dir"] = str(bd); c["claim"] = "C"; c["claim_type"] = "empirical"
    led.write_text(json.dumps(d))
    (bd / "recheck-semantic.json").write_text(json.dumps(
        {"verdict": "pass", "all_artifacts_reconfirmed": True, "significance": "borderline",
         "significance_confrontation": None}))
    (bd / "refute.json").write_text(json.dumps({"verdict": "clear"}))
    res = tmp_path / "rc.json"
    res.write_text(json.dumps([{"arxiv_id": "a", "key": "c0",
        "recheck": {"verdict": "pass", "all_artifacts_reconfirmed": True, "significance": "paper_worthy",
                    "significance_confrontation": {"strongest_rival_row": "FAKE"}},  # fabricated
        "refute": {"verdict": "clear"}}]))
    out = _run("apply-recheck", led, "W", round=1, result=str(res))
    assert out["killed"] == ["a:c0"] and out["converged"] == []
    assert json.loads(led.read_text())["papers"]["a"]["graveyard"][0]["kill_reason"] == "insignificant"


def test_finalize_round_cap_and_manifest(tmp_path):
    led = _seed_two_generated(tmp_path)  # paper 'a' still active with generated candidates
    out = _run("finalize", led, "W")
    assert out["status_counts"].get("exhausted_budget") == 1
    d = json.loads(led.read_text())["papers"]["a"]
    assert d["status"] == "exhausted_budget"
    # unspent candidates shelved
    assert all(c["status"] == "shelved" for c in d["candidates"].values())
    assert out["ideation_manifest"][0]["idea_count"] == 0


def test_begin_round_requeues_error_candidates(tmp_path):
    led = _seed_verified(tmp_path)
    d = json.loads(led.read_text())
    d["papers"]["a"]["candidates"]["c0"]["status"] = "error"
    d["papers"]["a"]["candidates"]["c0"]["error_note"] = "recheck agent returned nothing"
    d["papers"]["a"]["candidates"]["c1"]["status"] = "error"
    d["papers"]["a"]["candidates"]["c1"]["error_note"] = "verify infra"
    led.write_text(json.dumps(d))
    _run("begin-round", led, "W", round=2)
    cc = json.loads(led.read_text())["papers"]["a"]["candidates"]
    assert cc["c0"]["status"] == "verified"   # 'recheck' in note → back to verified
    assert cc["c1"]["status"] == "screened"   # else → back to screened
