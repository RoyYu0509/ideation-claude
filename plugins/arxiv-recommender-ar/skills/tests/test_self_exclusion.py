"""Self-author exclusion at ingest (build_shared_cache._exclude_self_authored and the
record oai_ingest writes into the pool).

A website-only profile writes papers.json with author_name = null, which leaves
researcher.author_aliases as the only name source. With both empty the filter must warn
and the pool must say so (self_exclusion.names == []) instead of passing silently; with an
alias set it must drop the researcher's papers although author_name is null.
"""
import json
import sys

import pytest

import build_shared_cache
import oai_ingest
from lib import arxiv_oai, config

OWN = {"arxiv_id": "2608.19797", "authors": ["Taylor Wu", "Jane Doe"],
       "categories": ["math.NA"], "submitted": "2026-08-20T08:49:31+00:00"}
COAUTHORS_ONLY = {"arxiv_id": "2607.29021",
                  "authors": ["Sam Lee", "Kim Park", "Pat Kim", "Alex Roe"],
                  "categories": ["math.NA"], "submitted": "2026-08-21T04:48:02+00:00"}


@pytest.fixture
def website_only(tmp_path, monkeypatch):
    """A data root whose profile was built website-only: papers.json author_name is null."""
    monkeypatch.setenv("AR_DATA_ROOT", str(tmp_path))
    prof = tmp_path / "data" / "profile"
    prof.mkdir(parents=True)
    (prof / "papers.json").write_text(json.dumps(
        {"s2_author_id": None, "author_name": None, "papers": []}))
    (prof / "profile.json").write_text(json.dumps({"arxiv_categories": ["math.NA"]}))
    return tmp_path


@pytest.fixture
def cfg_with(write_config):
    return lambda aliases: config.load_config(
        write_config(overrides={"researcher.author_aliases": aliases}))


def test_empty_name_set_warns_and_drops_nothing(website_only, cfg_with, capsys):
    kept, record = build_shared_cache._exclude_self_authored([OWN, COAUTHORS_ONLY], cfg_with([]))
    assert kept == [OWN, COAUTHORS_ONLY]
    assert record == {"names": [], "dropped": []}
    assert "WARNING" in capsys.readouterr().err


def test_alias_drops_own_papers_when_author_name_is_null(website_only, cfg_with, capsys):
    kept, record = build_shared_cache._exclude_self_authored(
        [OWN, COAUTHORS_ONLY], cfg_with(["jane DOE"]))
    assert kept == [COAUTHORS_ONLY]  # frequent coauthors alone never trigger the filter
    assert record == {"names": ["jane doe"], "dropped": ["2608.19797"]}
    assert "WARNING" not in capsys.readouterr().err


def test_papers_json_author_name_unions_with_aliases(website_only, cfg_with):
    (website_only / "data" / "profile" / "papers.json").write_text(
        json.dumps({"author_name": "Alex Roe", "papers": []}))
    kept, record = build_shared_cache._exclude_self_authored(
        [OWN, COAUTHORS_ONLY], cfg_with(["Jane Doe"]))
    assert kept == []
    assert record["names"] == ["alex roe", "jane doe"]


def test_oai_ingest_writes_the_record_into_the_pool(website_only, cfg_with, monkeypatch):
    cfg = cfg_with(["Jane Doe"])
    monkeypatch.setattr(config, "load_config", lambda *a, **k: cfg)
    monkeypatch.setattr(arxiv_oai, "list_sets", lambda: [])
    monkeypatch.setattr(arxiv_oai, "resolve_set", lambda cat, specs: "math:math:NA")
    monkeypatch.setattr(arxiv_oai, "harvest",
                        lambda spec, frm, until: [dict(OWN), dict(COAUTHORS_ONLY)])
    monkeypatch.setattr(sys, "argv", ["oai_ingest.py", "--end-utc", "2026-08-24", "--force"])
    assert oai_ingest.main() == 0
    pool = json.loads(
        (website_only / "data" / "cache" / "week-2026-W35-candidates.json").read_text())
    assert pool["self_exclusion"] == {"names": ["jane doe"], "dropped": ["2608.19797"]}
    assert [c["arxiv_id"] for c in pool["candidates"]] == ["2607.29021"]


def test_name_forms_and_reordered_accented_names_are_excluded(website_only, cfg_with):
    """papers.json name_forms count, and a name matches up to order / case / accents / punctuation;
    initials never match a full name."""
    (website_only / "data" / "profile" / "papers.json").write_text(json.dumps(
        {"author_name": "José García-López", "name_forms": ["Jose Garcia Lopez"], "papers": []}))
    def paper(axid, author):
        return {"arxiv_id": axid, "authors": [author], "categories": ["math.NA"],
                "submitted": "2026-09-01T00:00:00+00:00"}
    cands = [paper("2609.00001", "García-López, José"), paper("2609.00002", "Jose Garcia Lopez"),
             paper("2609.00003", "J. Garcia"), OWN]
    kept, record = build_shared_cache._exclude_self_authored(cands, cfg_with([]))
    assert [c["arxiv_id"] for c in kept] == ["2609.00003", "2608.19797"]   # no alias → the owner's paper stays
    assert record["dropped"] == ["2609.00001", "2609.00002"]
