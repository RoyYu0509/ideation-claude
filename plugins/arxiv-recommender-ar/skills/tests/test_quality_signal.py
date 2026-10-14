from unittest.mock import patch

from lib import quality_signal as q


# ── extract_repo_url ─────────────────────────────────────────────────────────

def test_extract_github_from_abstract():
    url, host, flags = q.extract_repo_url({"abstract": "Code at https://github.com/org/proj for all."})
    assert host == "github"
    assert url == "https://github.com/org/proj"
    assert "multi_repo" not in flags


def test_extract_strips_trailing_period_and_git():
    url, host, _ = q.extract_repo_url({"abstract": "See https://github.com/zjunlp/LightMem."})
    assert (url, host) == ("https://github.com/zjunlp/LightMem", "github")
    url2, _, _ = q.extract_repo_url({"comment": "repo: https://github.com/o/r.git"})
    assert url2 == "https://github.com/o/r"


def test_extract_dotted_repo_name_survives():
    url, _, _ = q.extract_repo_url({"abstract": "https://github.com/o/repo.js is here"})
    assert url == "https://github.com/o/repo.js"


def test_extract_comment_preferred_and_links():
    url, host, _ = q.extract_repo_url(
        {"comment": "https://github.com/a/b", "abstract": "no url", "links": ["https://github.com/c/d"]}
    )
    assert host == "github" and url == "https://github.com/a/b"


def test_extract_multi_repo_flag():
    _, _, flags = q.extract_repo_url({"abstract": "https://github.com/a/b and https://github.com/c/d"})
    assert "multi_repo" in flags


def test_extract_other_host_is_unverifiable_not_none():
    url, host, _ = q.extract_repo_url({"abstract": "data at https://zenodo.org/record/123"})
    assert host == "zenodo"
    assert url.startswith("https://zenodo.org/")


def test_extract_no_repo():
    url, host, _ = q.extract_repo_url({"abstract": "A purely theoretical a posteriori error analysis."})
    assert (url, host) == (None, None)


# ── classify_repo ────────────────────────────────────────────────────────────

def test_classify_active():
    out = q.classify_repo({"status": "active", "stars": 42, "pushed_at": "2026-01-01"}, "github")
    assert out["status"] == q.REPO_ACTIVE and out["stars"] == 42


def test_classify_dead():
    out = q.classify_repo({"status": "dead", "reason": "404"}, "github")
    assert out["status"] == q.REPO_DEAD


def test_classify_ratelimit_is_unverifiable():
    out = q.classify_repo({"status": "unverifiable", "reason": "ratelimit"}, "github")
    assert out["status"] == q.REPO_UNVERIFIABLE


def test_classify_non_github_host_unverifiable():
    assert q.classify_repo(None, "gitlab")["status"] == q.REPO_UNVERIFIABLE


def test_classify_no_host_is_no_repo():
    assert q.classify_repo(None, None)["status"] == q.REPO_NONE


# ── rollup_tier ──────────────────────────────────────────────────────────────

def test_rollup_strong_by_author():
    ann = q.QualityAnnotation(author_h_max=50)
    tier, flags = q.rollup_tier(ann, author_h_strong=30)
    assert tier == q.TIER_STRONG and "established_author" in flags


def test_rollup_strong_by_influence():
    ann = q.QualityAnnotation(influential_citation_count=12)
    tier, _ = q.rollup_tier(ann, infl_strong=5)
    assert tier == q.TIER_STRONG


def test_rollup_strong_by_active_repo():
    ann = q.QualityAnnotation(repo_status=q.REPO_ACTIVE, repo_stars=100)
    tier, flags = q.rollup_tier(ann)
    assert tier == q.TIER_STRONG and "repo_active" in flags


def test_rollup_no_repo_stays_neutral():
    ann = q.QualityAnnotation(repo_status=q.REPO_NONE, author_h_max=3)
    tier, _ = q.rollup_tier(ann, author_h_strong=30)
    assert tier == q.TIER_NEUTRAL


def test_rollup_unverifiable_stays_neutral():
    ann = q.QualityAnnotation(repo_status=q.REPO_UNVERIFIABLE)
    assert q.rollup_tier(ann)[0] == q.TIER_NEUTRAL


def test_rollup_dead_repo_is_weak():
    ann = q.QualityAnnotation(repo_status=q.REPO_DEAD)
    tier, flags = q.rollup_tier(ann)
    assert tier == q.TIER_WEAK and "repo_claimed_but_dead" in flags


def test_rollup_dead_repo_overrides_established_author():
    # Penalize precedence: a dead claimed repo is weak even for a famous author.
    ann = q.QualityAnnotation(repo_status=q.REPO_DEAD, author_h_max=80)
    assert q.rollup_tier(ann, author_h_strong=30)[0] == q.TIER_WEAK


# ── annotate (the 3 canonical cases, network mocked) ─────────────────────────

def test_annotate_famous_author_strong():
    cands = [{"arxiv_id": "2601.0001", "abstract": "no code here"}]
    with patch.object(q, "_s2_quality_batch", return_value={"2601.0001": {"h_max": 55}}):
        out = q.annotate(cands, cache_dir=None)
    assert out["2601.0001"].quality_tier == q.TIER_STRONG


def test_annotate_dead_repo_weak():
    cands = [{"arxiv_id": "2601.0002", "abstract": "Code: https://github.com/x/dead"}]
    with patch.object(q, "_s2_quality_batch", return_value={"2601.0002": {"h_max": 2}}), \
         patch.object(q, "github_check", return_value={"status": "dead", "reason": "404"}):
        out = q.annotate(cands, cache_dir=None)
    a = out["2601.0002"]
    assert a.repo_status == q.REPO_DEAD and a.quality_tier == q.TIER_WEAK


def test_annotate_no_repo_neutral():
    cands = [{"arxiv_id": "2601.0003", "abstract": "Pure numerical-analysis paper, no repo."}]
    with patch.object(q, "_s2_quality_batch", return_value={"2601.0003": {"h_max": 8}}):
        out = q.annotate(cands, cache_dir=None)
    a = out["2601.0003"]
    assert a.repo_status == q.REPO_NONE and a.quality_tier == q.TIER_NEUTRAL


def test_annotate_ratelimit_never_penalizes():
    cands = [{"arxiv_id": "2601.0004", "abstract": "Code: https://github.com/x/maybe"}]
    with patch.object(q, "_s2_quality_batch", return_value={}), \
         patch.object(q, "github_check", return_value={"status": "unverifiable", "reason": "ratelimit"}):
        out = q.annotate(cands, cache_dir=None)
    a = out["2601.0004"]
    assert a.repo_status == q.REPO_UNVERIFIABLE and a.quality_tier == q.TIER_NEUTRAL
