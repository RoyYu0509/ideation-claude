"""Verified-kill redesign (2026-07-11) — mechanical-layer + schema-v2 tests.

Covers the four deterministic anti-hack gates the redesign rests on, with the
W27 postmortem's canonical failure classes as regression fixtures:
  - the off-variety-spectrum premise (2607.01694-idea0 class): a 12-line numpy
    probe REFUTES the premise → probed_fail is committed evidence, not prose;
  - the stub-repo asset (2607.00196-idea0 class): a 2-file/1KB listing cannot
    evaluate live_verified no matter what the prose says;
  - the silent threshold relaxation (2.6x class): threshold_drift fires
    mechanically against the prior bundle;
  - the rho=0 wrong-direction rescope: rescope_without_probe fires when the
    routing set changes without an executed probe;
  - the fabricated-number substrate: every threshold needs a src anchor at
    WRITE time (ideate_io v2 + bundle_io).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from lib import asset_listing, bundle_io, ideate_io  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[2]

# ── shared fixture builders ───────────────────────────────────────────────────

SPECTRUM_PROBE = """\
import json
import numpy as np
rng = np.random.default_rng(0)
modes = np.array([[3 * np.pi, 7 * np.pi]])
assert modes.shape[0] >= 1 and np.abs(modes).sum() > 0, "degenerate input"
omega2 = modes[:, 0] ** 2
variety = modes[:, 1] ** 2 + 1.0
dist = float(np.abs(omega2 - variety).min() / 44.3)
print(f"min mode distance to variety = {dist:.3f} sigma")
print("PROBE_VERDICT: " + json.dumps({"id": "P1-spectrum", "pass": bool(dist <= 1.0),
                                      "value": round(dist, 6), "threshold": 1.0, "direction": "<="}))
"""


def run_probe(probe_dir: Path, suffix: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, AR_PROBE_DIR_OK="1", PROBE_TIMEOUT="60")
    cmd = ["bash", str(PLUGIN_ROOT / "bin" / "probe_run.sh"), str(probe_dir)]
    if suffix:
        cmd += ["--suffix", suffix]
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


@pytest.fixture()
def bundle_dir(tmp_path: Path) -> Path:
    """A minimal VALID bundle on disk: committed spectrum probe (probed_fail —
    the honest kill evidence), one dispositioned S2 hit, one non-live asset
    with a fallback."""
    bd = tmp_path / "bundles" / "9999.00001-c0"
    pd = bd / "probes" / "P1-spectrum"
    pd.mkdir(parents=True)
    (pd / "probe.py").write_text(SPECTRUM_PROBE)
    assert run_probe(pd).returncode == 0
    (bd / "assets").mkdir()
    (bd / "assets" / "repo.listing.json").write_text(json.dumps(
        {"listing": {"url": "https://github.com/x/y", "ok": True},
         "evaluation": {"status": "stub_or_empty"}}))
    return bd


def base_bundle() -> dict:
    return {
        "schema": 1, "week": "2026-W99", "arxiv_id": "9999.00001", "candidate_key": "c0",
        "round_born": 1, "working_title": "t", "claim": "X achieves Y under Z.",
        "claim_type": "empirical",
        "prior_art": {
            "queries": [
                {"id": "Q1", "tool": "s2_novelty", "mode": "search", "query": "a b c", "limit": 8,
                 "hits": [{"title": "Rival", "arxiv_id": "1911.06598", "year": 2019}]},
                {"id": "Q2", "tool": "s2_novelty", "mode": "related", "arxiv_id": "9999.00001",
                 "limit": 8, "hits": []},
            ],
            "diff_table": [
                {"rival": "Rival (arXiv:1911.06598)", "found_by": "Q1", "same_mechanism": False,
                 "same_task": True, "residual_delta": "ours dispersive; theirs elliptic",
                 "source_anchor": "arXiv:1911.06598 §2 p.3"}],
            "dispositions": [],
        },
        "premises": {
            "rows": [
                {"id": "P1", "premise": "benchmark spectrum lies on the characteristic variety",
                 "probe_class": "required", "status": "probed_fail",
                 "probe": {"id": "P1-spectrum", "dir": "probes/P1-spectrum",
                           "criterion": {"metric": "min mode distance (sigma)", "direction": "<=",
                                         "threshold": 1.0, "threshold_src": "src: paper Eq 4.2 jitter"}},
                 "consequence_if_false": "the mechanism dies"}],
            "falsifier": {
                "statement": "speedup < 10x refutes",
                "thresholds": [{"value": 10, "units": "x", "src": "src: arXiv:9999.00001 Table 1 p.5"}],
                "routes_through": ["P1"],
                "limit_analysis": {"can_trigger": "yes", "can_fail_to_trigger": "yes",
                                   "non_circular": "anchored on baseline table"}},
            "rescope_declarations": [],
        },
        "theory": None,
        "assets": [{"url": "https://github.com/x/y", "kind": "repo", "needed_for": "gen",
                    "needed_paths": ["gen/*.py"], "listing": "assets/repo.listing.json",
                    "status": "stub_or_empty", "fallback": "reimplement from Eq 4.2 spec"}],
        "artifacts": {"prior_art": "pass", "asset_check": "pass",
                      "premise_probe": "fail", "derivation_check": "not_applicable"},
    }


def v2_idea() -> dict:
    return {
        "working_title": "t", "claim": "c", "method_sketch": "m",
        "sharp_falsifier": "f", "significance_note": "s",
        "falsifier_thresholds": [{"value": 10, "units": "x", "src": "src: Table 1 p.5"}],
        "routes_through": ["P1"],
        "load_bearing_premises": [
            {"premise": "p", "status": "unverified", "probe": "compute the spectrum",
             "probe_class": "required",
             "criterion": {"metric": "sigma distance", "direction": "<=", "threshold": 1.0,
                           "threshold_src": "src: Eq 4.2"},
             "consequence_if_false": "dies"}],
        "asset_manifest": [
            {"url": "https://github.com/x/y", "kind": "repo", "needed_for": "gen",
             "needed_paths": ["gen/*.py"], "status": "unverified",
             "evidence": "declared — screen verifies"}],
    }


def v2_doc(idea=None) -> dict:
    return {"arxiv_id": "9999.00001", "week": "2026-W99", "title": "T",
            "paper_summary": "s", "why_relevant": "w", "ideas": [idea or v2_idea()]}


# ── ideate_io v2 (write-strict pre-registration) ─────────────────────────────

def test_v2_valid_idea_passes():
    ideate_io.validate_ideation(v2_doc(), strict_new=True)


def test_v2_missing_probe_class_fails():
    idea = v2_idea(); del idea["load_bearing_premises"][0]["probe_class"]
    with pytest.raises(ideate_io.IdeationSchemaError, match="probe_class"):
        ideate_io.validate_ideation(v2_doc(idea), strict_new=True)


def test_v2_required_without_criterion_fails():
    idea = v2_idea(); del idea["load_bearing_premises"][0]["criterion"]
    with pytest.raises(ideate_io.IdeationSchemaError, match="criterion"):
        ideate_io.validate_ideation(v2_doc(idea), strict_new=True)


def test_v2_threshold_without_src_fails():
    # the fabricated-number substrate: an unsourced threshold cannot even be WRITTEN
    idea = v2_idea(); idea["falsifier_thresholds"][0]["src"] = ""
    with pytest.raises(ideate_io.IdeationSchemaError, match="src"):
        ideate_io.validate_ideation(v2_doc(idea), strict_new=True)


def test_v2_route_through_deferrable_fails():
    # anti-circularity: anything the threshold depends on must be probe-executed
    idea = v2_idea(); idea["load_bearing_premises"][0]["probe_class"] = "deferrable"
    with pytest.raises(ideate_io.IdeationSchemaError, match="routes through"):
        ideate_io.validate_ideation(v2_doc(idea), strict_new=True)


def test_v2_asset_without_needed_paths_fails():
    idea = v2_idea(); del idea["asset_manifest"][0]["needed_paths"]
    with pytest.raises(ideate_io.IdeationSchemaError, match="needed_paths"):
        ideate_io.validate_ideation(v2_doc(idea), strict_new=True)


def test_load_all_ideations_skips_regen_rounds(tmp_path, monkeypatch):
    monkeypatch.setenv("AR_DATA_ROOT", str(tmp_path))
    d = tmp_path / "data" / "ideations" / "2026-W99"
    d.mkdir(parents=True)
    (d / "9999.00001.json").write_text(json.dumps({"arxiv_id": "9999.00001", "round": 1}))
    (d / "9999.00001-r2.json").write_text(json.dumps({"arxiv_id": "9999.00001", "round": 2}))
    out = ideate_io.load_all_ideations("2026-W99")
    assert out["9999.00001"]["round"] == 1, "a -r2 regen file must not overwrite the round-1 entry"


# ── probe_run.sh (sandboxed executor) ─────────────────────────────────────────

def test_probe_run_commits_verdict_and_meta(bundle_dir):
    pd = bundle_dir / "probes" / "P1-spectrum"
    v = bundle_io.read_probe_verdict(pd)
    # the 2607.01694 regression: the probe REFUTES the premise at ~8.9 sigma
    assert v["pass"] is False and 8.5 < v["value"] < 9.5
    meta = json.loads((pd / "meta.json").read_text())
    assert meta["exit_code"] == 0 and meta["sha256_script"]


def test_probe_run_blocks_network_imports(tmp_path):
    pd = tmp_path / "probes" / "bad"
    pd.mkdir(parents=True)
    (pd / "probe.py").write_text("import requests\nprint('PROBE_VERDICT: {}')\n")
    assert run_probe(pd).returncode == 5


def test_probe_run_requires_verdict_line(tmp_path):
    pd = tmp_path / "probes" / "silent"
    pd.mkdir(parents=True)
    (pd / "probe.py").write_text("print('no verdict here')\n")
    assert run_probe(pd).returncode == 3


# ── asset_listing.evaluate (the stub-repo kill substrate) ─────────────────────

def test_stub_repo_cannot_pass():
    # 2607.00196 regression: 2 files / 1KB, needed gen/*.py absent
    listing = {"ok": True, "files": [{"path": "README.md", "size": 800},
                                     {"path": "LICENSE", "size": 200}],
               "code_bytes": 0}
    ev = asset_listing.evaluate(listing, ["gen/*.py"])
    assert ev["status"] == "stub_or_empty"


def test_live_repo_passes():
    listing = {"ok": True,
               "files": [{"path": "gen/kg_manufactured.py", "size": 9000},
                         {"path": "solver/core.py", "size": 42000}],
               "code_bytes": 51000}
    assert asset_listing.evaluate(listing, ["gen/*.py"])["status"] == "live_verified"


def test_missing_repo_is_missing():
    assert asset_listing.evaluate({"ok": False, "error": "404"}, ["x"])["status"] == "missing"


# ── bundle_io (validating writer) ─────────────────────────────────────────────

def test_bundle_valid_writes(bundle_dir):
    bundle_io.validate_bundle(base_bundle(), bundle_dir)


def test_bundle_status_contradicting_verdict_fails(bundle_dir):
    b = base_bundle()
    b["premises"]["rows"][0]["status"] = "probed_pass"  # the committed verdict says pass=False
    with pytest.raises(bundle_io.BundleSchemaError, match="contradicts"):
        bundle_io.validate_bundle(b, bundle_dir)


def test_bundle_uncovered_hit_fails(bundle_dir):
    b = base_bundle()
    b["prior_art"]["queries"][0]["hits"].append({"title": "Hidden Rival", "arxiv_id": "2402.15419"})
    with pytest.raises(bundle_io.BundleSchemaError, match="disposition"):
        bundle_io.validate_bundle(b, bundle_dir)


def test_bundle_route_through_deferrable_fails(bundle_dir):
    b = base_bundle()
    b["premises"]["rows"][0]["probe_class"] = "deferrable"
    b["premises"]["rows"][0]["status"] = "unverified"
    b["premises"]["rows"][0]["probe"] = "later"
    with pytest.raises(bundle_io.BundleSchemaError):
        bundle_io.validate_bundle(b, bundle_dir)


def test_bundle_nonlive_asset_needs_fallback(bundle_dir):
    b = base_bundle()
    b["assets"][0]["fallback"] = ""
    with pytest.raises(bundle_io.BundleSchemaError, match="fallback"):
        bundle_io.validate_bundle(b, bundle_dir)


def test_bundle_threshold_without_src_fails(bundle_dir):
    b = base_bundle()
    b["premises"]["falsifier"]["thresholds"][0]["src"] = " "
    with pytest.raises(bundle_io.BundleSchemaError, match="src"):
        bundle_io.validate_bundle(b, bundle_dir)


# ── verify_bundle.py (V0 engine: drift + consistency + replay) ────────────────

def run_v0(bundle_dir: Path, rnd: int, extra: list[str]) -> dict:
    env = dict(os.environ, AR_PROBE_DIR_OK="1", PROBE_TIMEOUT="60")
    subprocess.run(
        ["bash", str(PLUGIN_ROOT / "bin" / "run_py.sh"),
         str(PLUGIN_ROOT / "scripts" / "verify_bundle.py"),
         "--bundle", str(bundle_dir), "--round", str(rnd), "--skip-network"] + extra,
        env=env, capture_output=True, text=True)
    return json.loads((bundle_dir / f"recheck-r{rnd}.json").read_text())


def write_bundle(bundle_dir: Path, b: dict) -> None:
    (bundle_dir / "bundle.json").write_text(json.dumps(b))


def codes(report: dict) -> set[str]:
    return {f["code"] for r in report["artifact_results"].values() for f in r["failures"]}


def test_v0_replay_passes(bundle_dir):
    write_bundle(bundle_dir, base_bundle())
    r = run_v0(bundle_dir, 1, [])
    assert r["all_pass"], r


def test_v0_threshold_drift_fires(bundle_dir, tmp_path):
    # the silent-2.6x-relaxation regression: prior round demanded 26x, current says 10x, no declaration
    write_bundle(bundle_dir, base_bundle())
    prev = base_bundle(); prev["premises"]["falsifier"]["thresholds"][0]["value"] = 26
    pv = tmp_path / "prev.json"; pv.write_text(json.dumps(prev))
    assert "threshold_drift" in codes(run_v0(bundle_dir, 2, ["--prev", str(pv)]))


def test_v0_rescope_without_probe_fires(bundle_dir, tmp_path):
    # the rho=0 regression: routing set grew with no declaration/probe
    write_bundle(bundle_dir, base_bundle())
    prev = base_bundle(); prev["premises"]["falsifier"]["routes_through"] = []
    pv = tmp_path / "prev.json"; pv.write_text(json.dumps(prev))
    assert "rescope_without_probe" in codes(run_v0(bundle_dir, 3, ["--prev", str(pv)]))


def test_v0_claim_drift_fires(bundle_dir, tmp_path):
    # the verifier may kill, never re-aim: bundle claim != generator claim
    write_bundle(bundle_dir, base_bundle())
    ideas = v2_doc(); ideas["ideas"][0]["claim"] = "a DIFFERENT claim"
    ip = tmp_path / "ideas.json"; ip.write_text(json.dumps(ideas))
    assert "claim_drift" in codes(run_v0(bundle_dir, 4, ["--ideas", str(ip), "--idea-index", "0"]))


def test_v0_tampered_probe_fires(bundle_dir):
    # committed verdict edited to pass=true → replay flips it (integrity event)
    b = base_bundle()
    pd = bundle_dir / "probes" / "P1-spectrum"
    out = (pd / "stdout.txt").read_text().replace('"pass": false', '"pass": true')
    (pd / "stdout.txt").write_text(out)
    b["premises"]["rows"][0]["status"] = "probed_pass"
    b["artifacts"]["premise_probe"] = "pass"
    write_bundle(bundle_dir, b)
    r = run_v0(bundle_dir, 5, [])
    assert "verdict_flip" in codes(r) and not r["all_pass"]


# ── ideate_save round-suffix preservation (shakedown F1 regression) ───────────

def _run_save(tmp_path, out_name, kind="ideation"):
    draft = tmp_path / "draft.json"
    if kind == "ideation":
        draft.write_text(json.dumps(v2_doc()))
    else:
        draft.write_text(json.dumps({"arxiv_id": "9999.00001", "week": "2026-W99",
                                     "pdf_quotes": [{"quote": "q", "why_useful": "w"}],
                                     "websearch_findings": [{"takeaway": "t"}],
                                     "rejected_candidates": [{"working_title": "x", "why_rejected": "y"}],
                                     "cross_thread_hints": []}))
    r = subprocess.run(
        ["bash", str(PLUGIN_ROOT / "bin" / "run_py.sh"),
         str(PLUGIN_ROOT / "scripts" / "lib" / "ideate_save.py"),
         "--in", str(draft), "--out", str(tmp_path / out_name), "--kind", kind,
         "--title", "T"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return Path(r.stdout.strip().splitlines()[-1]).name


def test_ideate_save_preserves_round_suffix(tmp_path):
    # F1: a round-2 write must NOT clobber the round-1 canonical file
    assert _run_save(tmp_path, "9999.00001-r2.json") == "9999.00001-r2.json"


def test_ideate_save_still_normalizes_legacy_suffix(tmp_path):
    assert _run_save(tmp_path, "9999.00001-ideation.json") == "9999.00001.json"


def test_ideate_save_evidence_round_suffix(tmp_path):
    assert _run_save(tmp_path, "evidence-9999.00001-r3.json", kind="evidence") \
        == "evidence-9999.00001-r3.json"
