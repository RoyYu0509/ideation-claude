"""On-disk-cached sentence-transformer embedding helper."""
from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np


def _warn(msg: str) -> None:
    bar = "!" * 72
    print(f"\n{bar}\n[embeddings] WARNING: {msg}\n{bar}", file=sys.stderr)


def _cache_root() -> Path:
    from .config import cache_dir
    p = cache_dir() / "embeddings"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _model_slug(model_name: str) -> str:
    return model_name.replace("/", "__").replace(":", "_")


def _key(model_name: str, text: str, backend: str, pooling: str = "mean") -> str:
    # `backend` AND `pooling` are part of the key: local vs hf_api, and cls- vs
    # mean-pooled vectors for the same (model, text) are NOT interchangeable, so they
    # must never share a cache slot. Measured on W31: cls and mean share only 5/10 of
    # the dense top-10 (Spearman 0.744) — a stale hit would silently mix two spaces.
    h = hashlib.sha256()
    h.update(backend.encode("utf-8"))
    h.update(b"\x00")
    h.update(pooling.encode("utf-8"))
    h.update(b"\x00")
    h.update(model_name.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def _cache_path(model_name: str, key: str, backend: str, pooling: str = "mean") -> Path:
    # backend and pooling are also directory levels so the caches are inspectable
    # (and independently deletable) on disk.
    sub = _cache_root() / backend / pooling / _model_slug(model_name) / key[:2]
    sub.mkdir(parents=True, exist_ok=True)
    return sub / f"{key}.npy"


_model_singletons: dict[tuple[str, str], object] = {}


def _load_model(model_name: str, pooling: str):
    """Build a SentenceTransformer with an EXPLICIT pooling head.

    Never `SentenceTransformer(model_name)` bare: a hub repo without a
    sentence-transformers config (allenai/specter2_base is one — it ships no
    modules.json and no 1_Pooling/) makes the library silently invent a MEAN
    pooling head. SPECTER/SPECTER2 put their citation-triplet loss on the [CLS]
    position, so mean-pooling averages token states that were never trained to be
    document vectors. Constructing the modules ourselves makes the choice explicit
    and config-driven, and it fails loudly instead of guessing.
    """
    cache_key = (model_name, pooling)
    if cache_key in _model_singletons:
        return _model_singletons[cache_key]
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.models import Pooling, Transformer
    word = Transformer(model_name)
    # sentence-transformers renamed this in 5.x; support both without pinning.
    get_dim = getattr(word, "get_embedding_dimension", None) or word.get_word_embedding_dimension
    pool = Pooling(get_dim(), pooling_mode=pooling)
    model = SentenceTransformer(modules=[word, pool])
    _model_singletons[cache_key] = model
    return model


def _encode_via_hf_api(model_name: str, texts: list[str], pooling: str) -> np.ndarray:
    """Encode via the HF serverless Inference API, one text at a time.

    feature_extraction returns either a pooled (dim,) vector OR a raw per-token
    (seq, dim) matrix, depending on the model's hub config. Models without a
    Sentence-Transformers/pooling config (e.g. allenai/specter2_base) return the
    token matrix; we mean-pool it to match the local backend. Calling one text at
    a time avoids the ragged-batch crash inside huggingface_hub when sequence
    lengths differ. No fallback to a different model or to the local backend —
    if it can't work, it raises.
    """
    from huggingface_hub import InferenceClient
    if "HF_TOKEN" not in os.environ:
        raise RuntimeError(
            "prefetch.embedding_backend is 'hf_api' but HF_TOKEN is not set in the environment. "
            "Either export HF_TOKEN before running, or change prefetch.embedding_backend "
            "to 'local' in config/config.yaml (human operator action required)."
        )
    client = InferenceClient(provider="hf-inference", token=os.environ["HF_TOKEN"])
    vecs: list[np.ndarray] = []
    for t in texts:
        r = np.asarray(client.feature_extraction(t, model=model_name), dtype=np.float32)
        if r.ndim == 2:        # (seq, dim) token-level → pool exactly as configured
            v = r[0] if pooling == "cls" else r.mean(axis=0)
        elif r.ndim == 1:      # (dim,) already pooled BY THE HUB — we cannot re-pool it
            if pooling == "cls":
                raise ValueError(
                    f"hf_api feature_extraction({model_name}) returned an already-pooled "
                    f"(dim,) vector, so prefetch.embedding_pooling='cls' cannot be honoured "
                    f"(the token states are gone). Use embedding_backend: local, or set "
                    f"embedding_pooling: mean and accept the hub's own pooling."
                )
            v = r
        else:
            raise ValueError(
                f"hf_api feature_extraction({model_name}) returned ndim={r.ndim} "
                f"shape={r.shape}; expected 1 (pooled) or 2 (token-level). Refusing to guess."
            )
        vecs.append(v)
    return np.stack(vecs, axis=0).astype(np.float32)


def _warn_on_truncation(model, texts: list[str], model_name: str) -> None:
    """Say out loud when the encoder is silently dropping the tail of an input.

    SentenceTransformer truncates at `max_seq_length` without a word. That is fine
    for the odd long abstract, but it is NOT fine for a query: the profile query is
    one long string, so a silent truncation would drop whole research threads from
    the dense tower and nothing would ever say so. Measured on W31: candidates hit
    the cap 4/1434 times (0.3%), while the profile query sat at 440 of 512 tokens —
    86% of the budget, i.e. two more threads away from silent loss.
    """
    limit = getattr(model, "max_seq_length", None)
    if not limit:
        return
    tok = model.tokenizer
    lens = [len(tok(t, add_special_tokens=True, truncation=False)["input_ids"]) for t in texts]
    over = [n for n in lens if n > limit]
    if over:
        _warn(f"{model_name}: {len(over)}/{len(texts)} texts exceed max_seq_length="
              f"{limit} and are TRUNCATED (longest {max(over)} tokens). Long single "
              f"inputs (the profile query) lose their tail silently — shorten them.")
    elif lens and max(lens) > 0.85 * limit:
        _warn(f"{model_name}: longest input is {max(lens)}/{limit} tokens "
              f"({100*max(lens)/limit:.0f}% of the cap). Not truncated yet — but a "
              f"slightly longer profile would be, without any error.")


def encode(
    model_name: str,
    texts: Iterable[str],
    *,
    backend: str,
    pooling: str,
    batch_size: int = 64,
    max_age_days: int | None = None,
) -> np.ndarray:
    """Encode `texts` with `model_name` on `backend`, caching each vector on disk.

    `backend` ("local" | "hf_api") and `pooling` ("cls" | "mean") are both REQUIRED
    — there is no default and no env-var fallback, so both are always explicit, and
    both are part of the cache key. `pooling` must match how the model was trained;
    see prefetch.embedding_pooling in config.yaml. Returns (N, D) float32 in input
    order.
    If `max_age_days` is set, cached vectors older than that many days are
    re-encoded (force-refresh).
    """
    if backend not in ("local", "hf_api"):
        raise ValueError(f"unknown embedding backend {backend!r}; expected 'local' or 'hf_api'")
    if pooling not in ("cls", "mean"):
        raise ValueError(f"unknown embedding pooling {pooling!r}; expected 'cls' or 'mean'")
    text_list = list(texts)
    if not text_list:
        return np.zeros((0, 0), dtype=np.float32)
    keys = [_key(model_name, t, backend, pooling) for t in text_list]
    paths = [_cache_path(model_name, k, backend, pooling) for k in keys]
    cached = [p.exists() for p in paths]
    if max_age_days is not None:
        cutoff = time.time() - max_age_days * 86400
        cached = [
            hit and paths[i].stat().st_mtime >= cutoff
            for i, hit in enumerate(cached)
        ]

    vectors: list[np.ndarray | None] = [None] * len(text_list)
    for i, (p, hit) in enumerate(zip(paths, cached)):
        if hit:
            vectors[i] = np.load(p)

    miss_idx = [i for i, hit in enumerate(cached) if not hit]
    if miss_idx:
        miss_texts = [text_list[i] for i in miss_idx]
        if backend == "hf_api":
            print(
                f"[embeddings] hf_api: encoding {len(miss_texts)} texts one-by-one "
                f"({pooling}-pooled) with {model_name} — slower than local; cached after "
                f"first run", file=sys.stderr,
            )
            new = _encode_via_hf_api(model_name, miss_texts, pooling)
        else:  # backend == "local" (validated above)
            model = _load_model(model_name, pooling)
            _warn_on_truncation(model, miss_texts, model_name)
            new = model.encode(
                miss_texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=False,
            ).astype(np.float32)
        for j, i in enumerate(miss_idx):
            vec = new[j]
            np.save(paths[i], vec)
            vectors[i] = vec

    return np.stack(vectors, axis=0)


def cosine_topk(query_vec: np.ndarray, doc_matrix: np.ndarray, k: int) -> list[tuple[int, float]]:
    if doc_matrix.size == 0:
        return []
    q = query_vec.astype(np.float32)
    d = doc_matrix.astype(np.float32)
    q_norm = q / (np.linalg.norm(q) + 1e-12)
    d_norm = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-12)
    sims = d_norm @ q_norm
    k = min(k, sims.shape[0])
    top_idx = np.argpartition(-sims, k - 1)[:k]
    top_idx = top_idx[np.argsort(-sims[top_idx])]
    return [(int(i), float(sims[i])) for i in top_idx]
