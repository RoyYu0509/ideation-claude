#!/usr/bin/env python3
"""scripts/rerank_llm.py — build / collect the LLM rerank (A0) and thread-quota final-select (G1 → TOP) units.

The orchestrator (workflows/arxiv-scout.js Phase 3) calls these in order; between a build-* and its collect-*
it spawns ONE agent per unit with the unit's SPAWN.md text. This script never calls a model.

    rerank_llm.py build-r0    --week W [--out-dir D] [--prefetched P] [--profile-dir PD] [--k 100]   # scout.rerank_pass=none
    rerank_llm.py build-a0    --week W [--out-dir D] [--prefetched P] [--profile-dir PD] [--k 100]   # scout.rerank_pass=a0
    rerank_llm.py collect-a0  --week W [--out-dir D] [--max-repair 0.05]
    rerank_llm.py build-g1    --week W [--out-dir D] [--promote-target 40]
    rerank_llm.py collect-g1  --week W [--out-dir D]
    rerank_llm.py build-top   --week W [--out-dir D] [--k <scout.rerank_return_n>]
    rerank_llm.py collect-top --week W [--out-dir D] [--k …] [--max-repair 0.05]

Defaults: D = <cache>/week-W-rerank-llm, P = <cache>/week-W-prefetched.json, PD = the instance's data/profile,
k(top) = scout.rerank_return_n (derived by lib/config). Each subcommand prints ONE JSON line (the last line of
stdout) that the orchestrator parses. A repair rate above --max-repair exits 3 (fail-closed: re-run the unit).
The logic lives in lib/rerank_llm.py, shared with report-v2/ablation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config as C  # noqa: E402
from lib import profile_io as PIO  # noqa: E402
from lib import rerank_llm as RL  # noqa: E402


def stage(a) -> RL.Stage:
    cfg = C.load_config()
    cache = C.cache_dir()
    out_dir = Path(a.out_dir) if a.out_dir else cache / f"week-{a.week}-rerank-llm"
    pref = Path(a.prefetched) if getattr(a, "prefetched", None) else cache / f"week-{a.week}-prefetched.json"
    pdir = PIO.resolve(a.profile_dir) if getattr(a, "profile_dir", None) else C.profile_dir()
    v, _ = PIO.load_view(pdir, cfg)
    if not pref.exists():
        raise SystemExit(f"[rerank_llm] {pref} not found — run prefetch.py first")
    with open(pref, encoding="utf-8") as f:
        cands = json.load(f)["candidates"]
    if not cands:
        raise SystemExit(f"[rerank_llm] {pref} has no candidates")
    st = RL.Stage(out_dir, a.week, v, pdir, cands)
    st.cfg = cfg
    return st


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("build-r0", "build-a0", "collect-a0", "build-g1", "collect-g1", "build-top", "collect-top"):
        q = sub.add_parser(c)
        q.add_argument("--week", required=True)
        q.add_argument("--out-dir", default=None)
        q.add_argument("--prefetched", default=None)
        q.add_argument("--profile-dir", default=None)
        if c in ("build-r0", "build-a0"):
            q.add_argument("--k", type=int, default=RL.TOP_K)
        if c == "build-g1":
            q.add_argument("--promote-target", type=int, default=RL.PROMOTE_TARGET)
        if c in ("build-top", "collect-top"):
            q.add_argument("--k", type=int, default=None, help="default: scout.rerank_return_n")
        if c.startswith("collect"):
            q.add_argument("--max-repair", type=float, default=0.05)
    a = ap.parse_args()
    st = stage(a)
    k_top = a.k if getattr(a, "k", None) else st.cfg.rerank_return_n
    try:
        if a.cmd == "build-r0":
            out = st.pass_through(k=a.k)
        elif a.cmd == "build-a0":
            out = st.build_a0(k=a.k)
        elif a.cmd == "collect-a0":
            out = st.collect_a0(max_repair=a.max_repair)
        elif a.cmd == "build-g1":
            out = st.build_g1(promote_target=a.promote_target)
        elif a.cmd == "collect-g1":
            out = st.collect_g1()
        elif a.cmd == "build-top":
            out = st.build_top(k=k_top)
        else:
            out = st.collect_top(k=k_top, max_repair=a.max_repair)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 3
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
