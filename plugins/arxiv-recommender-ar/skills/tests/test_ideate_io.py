"""Regression tests for the render-resilience + write-validation split.

Context: a weekly run wrote 16/20 ideation JSONs in a stale schema (top-level
`thread`, idea-level `title`/`falsifier`, no `paper_summary`) plus 2 with broken
JSON. The strict loader dropped all 18, so the digest rendered "ideation 尚未
运行" placeholders for papers whose ideas actually existed. The fix: the RENDER
path (load_all_ideations) is lenient + normalizing; the strict schema is enforced
on the WRITE path (save_ideation / ideate_save.py). These tests lock both halves.
"""
import json

import pytest

from lib import ideate_io


@pytest.fixture
def week_dir(tmp_path, monkeypatch):
    """Point config.data_dir() at a tmp tree and return the week's ideations dir."""
    monkeypatch.setenv("AR_DATA_ROOT", str(tmp_path))
    d = tmp_path / "data" / "ideations" / "2026-W99"
    (d / "refined").mkdir(parents=True)
    return d


def _write(d, name, text):
    (d / name).write_text(text, encoding="utf-8")


def test_normalize_maps_legacy_idea_fields():
    raw = {"arxiv_id": "x", "ideas": [{"title": "T", "falsifier": "F", "claim": "c"}]}
    out = ideate_io.normalize_ideation(raw)
    idea = out["ideas"][0]
    assert idea["working_title"] == "T"
    assert idea["sharp_falsifier"] == "F"
    # canonical key already present must win over the legacy alias
    raw2 = {"ideas": [{"title": "legacy", "working_title": "canon"}]}
    assert ideate_io.normalize_ideation(raw2)["ideas"][0]["working_title"] == "canon"
    # input not mutated
    assert "working_title" not in raw["ideas"][0]


def test_load_all_ideations_is_lenient(week_dir):
    # old-schema file (no paper_summary, idea uses title/falsifier) -> still loads
    _write(week_dir, "2599.00001-ideation.json", json.dumps({
        "arxiv_id": "2599.00001", "week": "2026-W99", "thread": "t",
        "ideas": [{"title": "WT", "claim": "c", "method_sketch": "m", "falsifier": "f"}],
    }))
    # broken JSON -> skipped, not crash
    _write(week_dir, "2599.00002-ideation.json", '{"arxiv_id":"2599.00002", BROKEN')
    # canonical good file
    _write(week_dir, "2599.00003.json", json.dumps({
        "arxiv_id": "2599.00003", "week": "2026-W99", "paper_summary": "p",
        "why_relevant": "w", "ideas": [{"working_title": "WT", "claim": "c",
        "method_sketch": "m", "sharp_falsifier": "f", "significance_note": "s"}],
    }))
    # sidecars must never be treated as ideations
    _write(week_dir, "evidence-2599.00003.json", json.dumps({"arxiv_id": "2599.00003"}))

    loaded = ideate_io.load_all_ideations("2026-W99")
    assert set(loaded) == {"2599.00001", "2599.00003"}      # broken skipped, sidecar ignored
    assert loaded["2599.00001"]["ideas"][0]["working_title"] == "WT"   # aliased on load


def test_find_ideation_file_accepts_both_names(week_dir):
    _write(week_dir, "2599.00009-ideation.json", "{}")      # legacy suffixed name
    assert ideate_io.find_ideation_file("2026-W99", "2599.00009") is not None
    assert ideate_io.find_ideation_file("2026-W99", "2599.99999") is None


def test_refined_fallback_extracts_title_and_seed(week_dir):
    _write(week_dir / "refined", "2599.00001-idea0.md",
           "# Plan\n**Working title:** 标题甲\n\nbody\n\n## /research Seed\n种子文本\n")
    fb = ideate_io.load_refined_fallback("2026-W99", "2599.00001")
    assert len(fb) == 1
    assert fb[0]["working_title"] == "标题甲"
    assert fb[0]["seed"] == "种子文本"


def test_save_path_stays_strict(week_dir):
    # the write contract must still reject a stale-schema dict (missing paper_summary)
    with pytest.raises(ideate_io.IdeationSchemaError):
        ideate_io.validate_ideation({"arxiv_id": "x", "week": "w",
            "ideas": [{"working_title": "t", "claim": "c", "method_sketch": "m",
                       "sharp_falsifier": "f", "significance_note": "s"}]})


def test_validate_evidence_happy_and_missing():
    import pytest
    ev = {
        "arxiv_id": "x", "week": "2026-W27",
        "pdf_quotes": [{"quote": "q", "why_useful": "w"}],
        "websearch_findings": [{"url": "u", "takeaway": "t"}],
        "rejected_candidates": [{"working_title": "t", "why_rejected": "r"}],
        "cross_thread_hints": [],
    }
    ideate_io.validate_evidence(ev)  # no raise
    bad = {k: v for k, v in ev.items() if k != "pdf_quotes"}
    with pytest.raises(ideate_io.IdeationSchemaError, match="pdf_quotes"):
        ideate_io.validate_evidence(bad)
    bad2 = dict(ev)
    bad2["websearch_findings"] = [{"url": "u"}]
    with pytest.raises(ideate_io.IdeationSchemaError, match="takeaway"):
        ideate_io.validate_evidence(bad2)
