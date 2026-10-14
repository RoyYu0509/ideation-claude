from lib import coverage_select as cs


def _pool(threads):
    # rerank order = list order; rank-1 is index 0
    return [{"arxiv_id": f"a{i}", "thread": t} for i, t in enumerate(threads)]


def _threads(chosen):
    return [p["thread"] for p in chosen]


# ── invariants shared by all modes ───────────────────────────────────────────

def test_rank1_always_first_all_modes():
    pool = _pool(["A", "A", "B", "C"])
    for mode in ("off", "stratify", "mmr"):
        chosen = cs.select(pool, 3, mode=mode)
        assert chosen[0]["arxiv_id"] == "a0", mode


def test_pool_smaller_than_n_returns_all():
    pool = _pool(["A", "B"])
    assert cs.select(pool, 5, mode="stratify") == pool


def test_off_is_thread_blind_slice():
    pool = _pool(["A", "A", "B", "C"])
    chosen = cs.select(pool, 3, mode="off")
    assert [p["arxiv_id"] for p in chosen] == ["a0", "a1", "a2"]
    assert _threads(chosen) == ["A", "A", "B"]  # concentrated — the bug


# ── stratify ─────────────────────────────────────────────────────────────────

def test_stratify_covers_distinct_threads():
    pool = _pool(["A", "A", "B", "A", "C", "B"])
    chosen = cs.select(pool, 3, mode="stratify")
    assert chosen[0]["arxiv_id"] == "a0"
    assert set(_threads(chosen)) == {"A", "B", "C"}  # 3 distinct vs off's {A,B}


def test_stratify_fills_when_fewer_threads_than_n():
    # Only 2 distinct threads but n=3 → must NOT invent a 3rd; fills by rerank order.
    pool = _pool(["A", "B", "A", "B"])
    chosen = cs.select(pool, 3, mode="stratify")
    assert chosen[0]["arxiv_id"] == "a0"
    assert set(_threads(chosen)) == {"A", "B"}
    assert len(chosen) == 3


def test_stratify_generic_over_many_threads():
    pool = _pool(["A", "B", "C", "D", "E"])
    chosen = cs.select(pool, 4, mode="stratify")
    assert len(chosen) == 4 and len(set(_threads(chosen))) == 4


def test_stratify_rotation_tiebreak_prefers_stale_thread():
    # rank-1 = A. New-thread candidates B (a1) and C (a2). B was just deep-dived
    # (recent), C is stale → rotation should pick C before B for the 2nd slot.
    pool = _pool(["A", "B", "C"])
    rotation = {"rotation_enabled": True, "last_deep_dive": {"B": 100, "C": 1}}
    chosen = cs.select(pool, 2, mode="stratify", rotation=rotation, current_week_idx=101)
    assert _threads(chosen) == ["A", "C"]


def test_stratify_rotation_off_keeps_rerank_order():
    pool = _pool(["A", "B", "C"])
    chosen = cs.select(pool, 2, mode="stratify")  # no rotation
    assert _threads(chosen) == ["A", "B"]


# ── mmr ──────────────────────────────────────────────────────────────────────

def test_mmr_diversifies_more_than_off():
    pool = _pool(["A", "A", "A", "B", "C"])
    off = set(_threads(cs.select(pool, 3, mode="off")))
    mmr = set(_threads(cs.select(pool, 3, mode="mmr", mmr_lambda=0.5)))
    assert len(mmr) >= len(off)
    assert "a0" == cs.select(pool, 3, mode="mmr")[0]["arxiv_id"]


def test_mmr_high_lambda_favors_relevance():
    # λ=1.0 → pure relevance → behaves like off (rerank order).
    pool = _pool(["A", "A", "B"])
    chosen = cs.select(pool, 2, mode="mmr", mmr_lambda=1.0)
    assert [p["arxiv_id"] for p in chosen] == ["a0", "a1"]


# ── rank_all: full coverage-ordered permutation (fill-to-N walk order) ────────

def test_rank_all_returns_full_permutation_ignoring_n():
    pool = _pool(["A", "A", "A", "B", "C"])
    chosen = cs.select(pool, 2, mode="stratify", rank_all=True)  # n=2 ignored
    assert len(chosen) == len(pool)
    assert {p["arxiv_id"] for p in chosen} == {p["arxiv_id"] for p in pool}


def test_rank_all_stratify_is_coverage_first_then_rerank_tail():
    # rank-1 (A), then one best per NEW thread (B, C), then the rerank tail (A,A).
    pool = _pool(["A", "A", "A", "B", "C"])
    chosen = cs.select(pool, 2, mode="stratify", rank_all=True)
    assert [p["arxiv_id"] for p in chosen] == ["a0", "a3", "a4", "a1", "a2"]


def test_rank_all_off_is_pure_rerank_order():
    pool = _pool(["A", "A", "B", "C"])
    chosen = cs.select(pool, 2, mode="off", rank_all=True)
    assert [p["arxiv_id"] for p in chosen] == ["a0", "a1", "a2", "a3"]


def test_rank_all_false_default_is_unchanged():
    # the existing one-shot select(pool, N) path must be byte-identical
    pool = _pool(["A", "A", "B", "C"])
    assert cs.select(pool, 3, mode="stratify") == cs.select(pool, 3, mode="stratify", rank_all=False)
    assert len(cs.select(pool, 3, mode="stratify")) == 3
