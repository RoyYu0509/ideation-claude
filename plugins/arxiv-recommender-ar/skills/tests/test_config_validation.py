"""Tests for the STRICT (zero-default) config loader.

config/config.yaml is the single source of truth: every key is required, a
missing key crashes naming it, and an invalid choice crashes (never a silent
fallback). The `write_config` fixture (conftest.py) starts from the real
tracked config and applies overrides/deletions.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib.config import ConfigError, load_config


def test_real_config_loads_and_invariants_hold(write_config):
    # No pinned tunables here — knob values drift with every retune (this test
    # used to pin prefetch=150 and went stale). Assert the STRUCTURAL
    # invariants the loader must guarantee instead.
    cfg = load_config(write_config())
    assert isinstance(cfg.prefetch_top_k, int) and cfg.prefetch_top_k > 0
    assert cfg.prefetch_top_k >= cfg.rerank_return_n >= 1
    assert cfg.embedding_backend in ("local", "hf_api")
    assert isinstance(cfg.rrf_k, int) and cfg.rrf_k > 0
    # io.* present and typed
    assert isinstance(cfg.io_s2_timeout, int) and cfg.io_s2_timeout > 0
    assert isinstance(cfg.io_arxiv_page_size, int) and cfg.io_arxiv_page_size > 0


def test_missing_required_key_raises_and_names_it(write_config):
    path = write_config(deletions=["scout.prefetch_top_k"])
    with pytest.raises(ConfigError, match="scout.prefetch_top_k"):
        load_config(path)


def test_missing_io_key_raises(write_config):
    path = write_config(deletions=["io.s2_timeout"])
    with pytest.raises(ConfigError, match="io.s2_timeout"):
        load_config(path)


def test_rrf_k_zero_raises(write_config):
    with pytest.raises(ConfigError, match="rrf_k must be > 0"):
        load_config(write_config(overrides={"prefetch.rrf_k": 0}))


def test_rrf_k_negative_raises(write_config):
    with pytest.raises(ConfigError, match="rrf_k must be > 0"):
        load_config(write_config(overrides={"prefetch.rrf_k": -5}))


def test_rerank_return_n_is_derived(write_config):
    # Full derivation (2026-07-05): rerank_return_n is NOT a config key — config.py
    # computes min(prefetch_top_k, 2*top_n_papers) (2026-09-19 修订 #11: was +1) and
    # injects it into raw for the JS spec / cfgval consumers.
    cfg = load_config(write_config(overrides={"scout.prefetch_top_k": 50, "scout.top_n_papers": 3}))
    assert cfg.rerank_return_n == 6
    assert cfg.raw["scout"]["rerank_return_n"] == 6
    capped = load_config(write_config(overrides={"scout.prefetch_top_k": 5, "scout.top_n_papers": 3}))
    assert capped.rerank_return_n == 5  # capped by the prefetch pool


def test_funnel_invariant_violation_raises(write_config):
    with pytest.raises(ConfigError, match="prefetch_top_k.*must be >="):
        load_config(write_config(overrides={"scout.prefetch_top_k": 1}))


def test_invalid_embedding_backend_raises(write_config):
    with pytest.raises(ConfigError, match="embedding_backend"):
        load_config(write_config(overrides={"prefetch.embedding_backend": "bogus"}))


def test_invalid_repo_dead_action_raises(write_config):
    with pytest.raises(ConfigError, match="repo_dead_action"):
        load_config(write_config(overrides={"quality.repo_dead_action": "nuke"}))


def test_missing_s2_and_website_raises(write_config):
    path = write_config(overrides={"researcher.s2_author_id": None,
                                   "researcher.personal_website": None,
                                   "researcher.google_scholar_url": None})
    with pytest.raises(ConfigError, match="s2_author_id, researcher.personal_website or"):
        load_config(path)


def test_null_optional_value_is_allowed(write_config):
    # dual_encoder_model: null is a real value (feature off), not a missing key.
    cfg = load_config(write_config(overrides={"prefetch.dual_encoder_model": None}))
    assert cfg.dual_encoder_model is None


def test_rerank_pass_is_a_strict_choice(write_config):
    # 2026-09-19 修订 #12: production = none (R0 won the pre-registered three-arm test); a0 stays selectable.
    assert load_config(write_config()).rerank_pass == "none"
    assert load_config(write_config(overrides={"scout.rerank_pass": "a0"})).rerank_pass == "a0"
    with pytest.raises(ConfigError, match="rerank_pass"):
        load_config(write_config(overrides={"scout.rerank_pass": "l1"}))
