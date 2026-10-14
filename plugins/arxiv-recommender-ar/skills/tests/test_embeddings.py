"""Tests for the embedding backend (A: HF pooling), cache key (B: backend +
pooling), and the explicit pooling head (C) — the 2026-09-08 regression."""
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import embeddings


# ── B: backend is part of the cache identity ─────────────────────────────────
def test_cache_key_includes_backend():
    assert embeddings._key("m", "t", "local") != embeddings._key("m", "t", "hf_api")


def test_cache_path_includes_backend(tmp_path):
    with patch.object(embeddings, "_cache_root", return_value=tmp_path):
        p_local = embeddings._cache_path("allenai/x", "abcd", "local")
        p_api = embeddings._cache_path("allenai/x", "abcd", "hf_api")
    assert "local" in p_local.parts and "hf_api" in p_api.parts
    assert p_local != p_api


def test_cache_key_includes_pooling():
    assert embeddings._key("m", "t", "local", "cls") != embeddings._key("m", "t", "local", "mean")


def test_cache_path_includes_pooling(tmp_path):
    with patch.object(embeddings, "_cache_root", return_value=tmp_path):
        p_cls = embeddings._cache_path("allenai/x", "abcd", "local", "cls")
        p_mean = embeddings._cache_path("allenai/x", "abcd", "local", "mean")
    assert "cls" in p_cls.parts and "mean" in p_mean.parts
    assert p_cls != p_mean


def test_unknown_backend_raises():
    with pytest.raises(ValueError, match="unknown embedding backend"):
        embeddings.encode("m", ["t"], backend="bogus", pooling="cls")


def test_unknown_pooling_raises():
    with pytest.raises(ValueError, match="unknown embedding pooling"):
        embeddings.encode("m", ["t"], backend="local", pooling="bogus")


# ── C: the pooling head is explicit, never inferred ──────────────────────────
# Regression for 2026-09-08: `SentenceTransformer(model_name)` on a hub repo with no
# sentence-transformers config (allenai/specter2_base) silently invents MEAN pooling,
# but SPECTER2's triplet loss is on [CLS]. The loader must construct the head itself.
def test_load_model_builds_explicit_pooling_head(monkeypatch):
    import sentence_transformers as st
    import sentence_transformers.models as stm
    seen = {}

    class _FakeTransformer:
        def __init__(self, name):
            seen["transformer_arg"] = name

        def get_word_embedding_dimension(self):
            return 768

    class _FakePooling:
        def __init__(self, dim, pooling_mode=None):
            seen["pool_dim"] = dim
            seen["pool_mode"] = pooling_mode

    def _fake_st(*args, **kwargs):
        seen["st_positional"] = args
        seen["st_modules"] = kwargs.get("modules")
        return object()

    monkeypatch.setattr(stm, "Transformer", _FakeTransformer)
    monkeypatch.setattr(stm, "Pooling", _FakePooling)
    monkeypatch.setattr(st, "SentenceTransformer", _fake_st)
    embeddings._model_singletons.clear()
    embeddings._load_model("allenai/specter2_base", "cls")

    assert seen["pool_mode"] == "cls", "pooling mode must be passed through, not inferred"
    assert seen["pool_dim"] == 768
    assert seen["st_positional"] == (), \
        "SentenceTransformer must NOT be called with a bare model name — that is the bug"
    assert len(seen["st_modules"]) == 2
    embeddings._model_singletons.clear()


def test_load_model_singleton_is_per_pooling(monkeypatch):
    import sentence_transformers as st
    import sentence_transformers.models as stm
    calls = []

    class _FakeTransformer:
        def __init__(self, name): pass
        def get_word_embedding_dimension(self): return 768

    monkeypatch.setattr(stm, "Transformer", _FakeTransformer)
    monkeypatch.setattr(stm, "Pooling", lambda dim, pooling_mode=None: object())
    monkeypatch.setattr(st, "SentenceTransformer",
                        lambda *a, **k: calls.append(1) or object())
    embeddings._model_singletons.clear()
    embeddings._load_model("m", "cls")
    embeddings._load_model("m", "cls")     # cached
    embeddings._load_model("m", "mean")    # different pooling => different model
    assert len(calls) == 2
    embeddings._model_singletons.clear()


# ── A: HF API pooling ────────────────────────────────────────────────────────
class _FakeClient:
    def __init__(self, ret):
        self._ret = ret

    def feature_extraction(self, text, model=None):
        return self._ret


def _encode_hf(tmp_path, ret, text="hello", pooling="mean"):
    with patch.object(embeddings, "_cache_root", return_value=tmp_path), \
         patch("huggingface_hub.InferenceClient", return_value=_FakeClient(ret)):
        return embeddings.encode("allenai/specter2_base", [text], backend="hf_api",
                                 pooling=pooling)


def test_hf_token_pools_token_matrix_by_mean(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "x")
    ret = np.array([[1.0, 2, 3, 4], [3, 4, 5, 6]], dtype=np.float32)  # (seq=2, dim=4)
    out = _encode_hf(tmp_path, ret)
    assert out.shape == (1, 4)
    np.testing.assert_allclose(out[0], ret.mean(axis=0))


def test_hf_passes_through_already_pooled_vector(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "x")
    ret = np.array([1.0, 2, 3, 4], dtype=np.float32)  # (dim,) already pooled
    out = _encode_hf(tmp_path, ret, text="world")
    assert out.shape == (1, 4)
    np.testing.assert_allclose(out[0], ret)


def test_hf_unexpected_shape_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "x")
    ret = np.zeros((2, 3, 4), dtype=np.float32)  # 3-D: refuse to guess
    with pytest.raises(ValueError, match="Refusing to guess"):
        _encode_hf(tmp_path, ret, text="three-d")


def test_hf_missing_token_raises_not_silent_local(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    ret = np.array([1.0, 2, 3, 4], dtype=np.float32)
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        _encode_hf(tmp_path, ret, text="no-token")


def test_hf_cls_pooling_takes_first_token(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "x")
    ret = np.array([[1.0, 2, 3, 4], [3, 4, 5, 6]], dtype=np.float32)  # (seq=2, dim=4)
    out = _encode_hf(tmp_path, ret, text="cls-2d", pooling="cls")
    np.testing.assert_allclose(out[0], ret[0])


def test_hf_cls_on_already_pooled_vector_raises(tmp_path, monkeypatch):
    # The hub pooled it for us, so the token states are gone and `cls` is a lie.
    monkeypatch.setenv("HF_TOKEN", "x")
    ret = np.array([1.0, 2, 3, 4], dtype=np.float32)
    with pytest.raises(ValueError, match="cannot be honoured"):
        _encode_hf(tmp_path, ret, text="cls-1d", pooling="cls")
