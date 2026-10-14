"""Every verified survivor of a paper reaches the weekly report (2026-09-12).

arxiv-ideation.js PLAN writes one refined plan per SURVIVOR — refined/<id>-idea<N>.md is the paper's N-th
converged candidate in ledger order — so the report renders a card for each one, not only the first, and
whatever the paper settled as (a 1-round week rarely reaches survivor_target, so most survivors sit in
exhausted_budget papers).
"""
from lib import scout_digest, scout_web


def _paper(statuses, status="exhausted_budget"):
    return {"status": status, "graveyard": [],
            "candidates": {f"c{i + 1}": {"status": st, "working_title": f"title {i}", "claim": f"claim {i}"}
                           for i, st in enumerate(statuses)}}


def _fake_plans(monkeypatch, module, fn_name):
    seen = []

    def fake(week, axid, n):
        seen.append(n)
        return f"# plan {n}\n\n## /research Seed\n\nseed-{n}\n"
    monkeypatch.setattr(module, fn_name, fake)
    return seen


def test_converged_candidates_keep_ledger_order():
    lp = _paper(["converged", "killed", "converged"])
    assert [c["claim"] for c in scout_web._converged_candidates(lp)] == ["claim 0", "claim 2"]


def test_web_renders_every_survivor_with_its_own_plan(monkeypatch):
    seen = _fake_plans(monkeypatch, scout_web, "_load_refined")
    lp = _paper(["converged", "killed", "converged"])
    _badge, ideas_html, _grave, n = scout_web._render_ledger_section(lp, "2026-W37", "2609.00001")
    assert n == 2
    assert seen == [0, 1]                       # card N reads idea<N-1>, in ledger order
    assert "claim 0" in ideas_html and "claim 2" in ideas_html
    assert "claim 1" not in ideas_html          # a killed candidate is never shown as a survivor


def test_digest_renders_every_survivor_whatever_the_paper_settled_as(monkeypatch):
    seen = []
    monkeypatch.setattr(scout_digest, "_load_survivor_seed",
                        lambda week, axid, n=0: seen.append(n) or f"seed-{n}")
    lp = _paper(["converged", "killed", "converged"])      # exhausted_budget, 2 survivors
    out = "\n".join(scout_digest._render_ledger_paper(lp, None, "", "2026-W37", "2609.00001"))
    assert "claim 0" in out and "claim 2" in out and "claim 1" not in out
    assert seen == [0, 1] and "seed-1" in out
    assert "本周未产出幸存 idea" not in out


def test_web_no_survivor_is_an_exhaustion_line():
    _badge, ideas_html, _grave, n = scout_web._render_ledger_section(_paper(["killed"]), "2026-W37", "2609.00001")
    assert n == 0 and "本周未产出幸存 idea" in ideas_html
