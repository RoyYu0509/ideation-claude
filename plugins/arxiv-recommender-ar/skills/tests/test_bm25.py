from lib import bm25


def test_tokenize_strips_stopwords_and_short_tokens():
    out = bm25.tokenize("We propose a novel method for graph neural networks.")
    assert "graph" in out
    assert "neural" in out
    assert "networks" in out
    assert "we" not in out
    assert "a" not in out
    assert "propose" not in out
    assert "novel" not in out
    assert "method" not in out


def test_tokenize_lowercases_and_handles_hyphens():
    out = bm25.tokenize("Cross-Attention with Self-Supervised Pretraining")
    assert "cross-attention" in out
    assert "self-supervised" in out
    assert "pretraining" in out


def test_rank_returns_topk_pairs():
    docs = [
        "graph neural networks for molecules",
        "language model finetuning recipes",
        "graph convolution and message passing for chemistry",
        "image diffusion noise schedules",
    ]
    query = ["graph", "molecules", "chemistry"]
    top = bm25.rank(query, docs, top_k=2)
    assert len(top) == 2
    idxs = {i for i, _ in top}
    # The two graph-themed docs should win.
    assert idxs == {0, 2}


def test_rank_empty_docs():
    assert bm25.rank(["foo"], [], top_k=5) == []


# ── phrase mode (REC-SYSTEM-V2 A4; whole-phrase matching since 2026-09-13) ─────

def test_phrase_terms_are_whole_phrases_deduplicated():
    terms = bm25.phrase_terms(["finite element method", "Finite element methods", "physics-informed neural networks",
                               "quasicontinuum", "a posteriori error estimates"])
    # one term per phrase: plural folded, hyphen split, only function words dropped ("method" stays)
    assert terms == ["finite_element_method", "physic_informed_neural_network", "quasicontinuum",
                     "posteriori_error_estimate"]


def test_phrase_mode_matches_whole_phrases_only():
    docs = ["We study the finite element method for elasticity.",
            "A finite sample bound; each element of the set is small.",
            "Graph neural networks for molecules.",
            "Physics-informed neural networks for PDEs."]
    top = dict(bm25.rank(bm25.phrase_terms(["finite element method", "physics-informed neural networks"]),
                         docs, top_k=4, phrases=True))
    assert top[0] > 0 and top[3] > 0
    assert top[1] == 0                                 # the words, but not adjacent
    assert top[2] == 0                                 # the fragment "neural networks" alone never matches


def test_tokenize_phrases_adds_one_token_per_occurrence():
    toks = bm25.tokenize_phrases("Random features; random feature models.", ["random_feature", "feature_model"])
    assert toks.count("random_feature") == 2 and toks.count("feature_model") == 1
    assert toks[:5] == ["random", "feature", "random", "feature", "model"]


def test_legacy_tokenize_is_untouched_by_phrase_mode():
    assert bm25.tokenize("physics-informed networks") == ["physics-informed", "networks"]
