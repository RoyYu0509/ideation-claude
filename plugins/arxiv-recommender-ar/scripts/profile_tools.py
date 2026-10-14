#!/usr/bin/env python3
"""The deterministic half of a profile build (v3, 2026-09-16). Needs only papers.json, so the arxiv-profile
builder starts it in the background and writes its own judgement parts meanwhile.

Every output records the sha256 of the papers.json it was computed from; profile_finalize.py refuses a part
built from a different papers.json. Every step runs even when an earlier one fails; each step's outcome
lands in parts/_tools.json and a failed step never falls back to a weaker substitute (no weekly pool ⇒ no
extracted keywords, not keywords ranked without a background corpus).

  data/profile/parts/keywords_extracted.json   lib/keyphrases against the newest weekly candidate pool
  data/profile/parts/categories.json           which arXiv categories to fetch each week
  data/profile/ref_abstracts.json              S2 title/abstract of every reference cited by >= 2 core papers
  data/profile/citation-graph.json             scripts/build_citation_graph.py --if-stale
  data/profile/parts/_tools.json               per-step status

Usage: bin/run_py.sh scripts/profile_tools.py [--pool <week-*-candidates.json>] [--only STEP[,STEP]]
Exit 0 only when every requested step succeeded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import channel_spec as CS  # noqa: E402
from lib import config, keyphrases, s2_client  # noqa: E402
from lib import profile_papers as PP  # noqa: E402

STEPS = ("keywords_extracted", "categories", "ref_abstracts", "citation_graph")
REF_FIELDS = ("paperId", "title", "abstract", "year", "publicationDate", "externalIds")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def newest_pool(data_root: Path) -> Path | None:
    pools = sorted((data_root / "data" / "cache").glob("week-*-candidates.json"))
    return pools[-1] if pools else None


def step_keywords(papers: list[dict], papers_sha: str, pool: Path | None, cfg, out: Path) -> str:
    if pool is None or not pool.exists():
        raise RuntimeError("no weekly candidate pool (data/cache/week-*-candidates.json) — the extractor needs one "
                           "as its background corpus; run a weekly fetch first or pass --pool")
    cands = json.loads(pool.read_text(encoding="utf-8"))["candidates"]
    if not cands:
        raise RuntimeError(f"weekly pool {pool.name} is empty")
    own = [CS.text_of(p) for p in papers if not p.get("peripheral") and (p.get("abstract") or "").strip()]
    rows = keyphrases.extract(own, [CS.text_of(c) for c in cands], k=cfg.profile_n_keyphrases)
    # no phrase printed by >= 2 own papers is this researcher's data, not a tool failure: the part is written
    # with zero rows and the coverage check reports bm25:b4 as EMPTY
    _write(out, {"papers_sha256": papers_sha, "built_at": _now(), "rows": rows,
                 "note": (f"lib/keyphrases.extract: 1–3-word phrases printed by >= 2 of the {len(own)} own papers, "
                          f"ranked by rarity against {len(cands)} papers of {pool.name}, top {cfg.profile_n_keyphrases}"),
                 "pool": {"file": pool.name, "sha256": sha256_file(pool), "size": len(cands)}})
    return f"{len(rows)} phrases against {pool.name} ({len(cands)} papers)" + ("" if rows else " — EMPTY")


def step_categories(papers: list[dict], papers_sha: str, cfg, out: Path) -> str:
    core = [p for p in papers if not p.get("peripheral")]
    derived, table = PP.derive_categories(core, cfg.profile_category_min_primary, cfg.profile_category_min_cross)
    override = list(cfg.arxiv_categories_override or [])
    if cfg.arxiv_categories_fixed:
        chosen, note = override, "fixed by researcher.arxiv_categories (arxiv_categories_fixed: true)"
    else:
        chosen = CS.dedup(derived + override)
        note = (f"derived from own papers' arXiv categories (primary >= {cfg.profile_category_min_primary} "
                f"or listed >= {cfg.profile_category_min_cross}); config-appended: "
                f"{[c for c in override if c not in derived] or 'none'}")
    if not chosen:
        raise RuntimeError("no arXiv categories: no own paper carries one and researcher.arxiv_categories is empty")
    _write(out, {"papers_sha256": papers_sha, "built_at": _now(), "chosen": chosen, "note": note, "table": table})
    return f"{len(chosen)} categories: {chosen}"


def step_ref_abstracts(papers: list[dict], papers_sha: str, out: Path,
                       ref_cutoff: str | None = None) -> str:
    """`--ref-cutoff T` 丢掉 publicationDate >= T 的参考文献;**无日期的保留并计数**。

    为什么必须有这个开关:时间截断实验里,`thread:members_refs` 是**生产臂的通道**,
    而这份文件的参考文献来自 S2 的当前记录 —— 论文改版后新增的、T 之后发表的参考文献会
    直接流进被测通道。`publicationDate` 一直抓着却没人用(EVAL-PLAN 修订 #16 §3.6 泄漏 ④,登记为必修)。
    无日期的保留而不是丢弃:丢掉会把「S2 没记日期」当成「T 之后发表」,那是另一种偏差,
    而且数量会记在 `n_undated_kept` 里,可审计。"""
    ids = CS.ref_ids(papers)
    rows = s2_client.papers_batch(ids, fields=REF_FIELDS) if ids else []   # S2 failures raise — a real tool failure
    refs, n_dropped, n_undated = {}, 0, 0
    for rid, m in zip(ids, rows):
        if not m:
            continue
        d = (m.get("publicationDate") or "")[:10]
        if ref_cutoff:
            if not d:
                n_undated += 1
            elif d >= ref_cutoff:
                n_dropped += 1
                continue
        refs[rid] = {k: m.get(k) for k in ("title", "abstract", "year", "publicationDate", "externalIds")}
    n_abs = sum(1 for m in refs.values() if (m.get("abstract") or "").strip())
    _write(out, {"papers_sha256": papers_sha, "built_at": _now(), "min_papers": CS.REFS_MIN_PAPERS,
                 "ref_cutoff": ref_cutoff, "n_dropped_after_cutoff": n_dropped, "n_undated_kept": n_undated,
                 "n_ids": len(ids), "n_found": len(refs), "n_with_abstract": n_abs, "refs": refs})
    tail = (f" · cutoff {ref_cutoff}: dropped {n_dropped}, kept {n_undated} undated" if ref_cutoff else "")
    return f"{n_abs}/{len(ids)} references with an abstract{tail}" + ("" if n_abs else " — EMPTY")


def step_citation_graph(papers_path: Path, out: Path) -> str:
    script = Path(__file__).resolve().parent / "build_citation_graph.py"
    r = subprocess.run([sys.executable, str(script), "--papers", str(papers_path), "--out", str(out), "--if-stale"],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"build_citation_graph.py exited {r.returncode}: {(r.stderr or r.stdout)[-400:]}")
    return (r.stderr.strip().splitlines() or ["ok"])[-1][:200]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool", type=Path, default=None, help="default: the newest data/cache/week-*-candidates.json")
    ap.add_argument("--only", default=",".join(STEPS), help=f"comma-separated subset of {STEPS}")
    ap.add_argument("--ref-cutoff", default=None, metavar="YYYY-MM-DD",
                    help="drop references published on/after this date (undated ones are kept and counted); "
                         "required by time-truncated evaluations — thread:members_refs is a deployed channel")
    a = ap.parse_args()
    steps = [s.strip() for s in a.only.split(",") if s.strip()]
    bad = [s for s in steps if s not in STEPS]
    if bad:
        raise SystemExit(f"[profile_tools] unknown step(s) {bad}; choose from {STEPS}")

    cfg = config.load_config()
    pdir = config.profile_dir()
    papers_path = pdir / "papers.json"
    if not papers_path.exists():
        raise SystemExit(f"[profile_tools] {papers_path} not found — build papers.json first")
    papers = json.loads(papers_path.read_text(encoding="utf-8"))["papers"]
    papers_sha = sha256_file(papers_path)
    parts = pdir / "parts"
    status_path = parts / "_tools.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    pool = a.pool or newest_pool(pdir.parents[1])

    jobs = {
        "keywords_extracted": lambda: step_keywords(papers, papers_sha, pool, cfg, parts / "keywords_extracted.json"),
        "categories": lambda: step_categories(papers, papers_sha, cfg, parts / "categories.json"),
        "ref_abstracts": lambda: step_ref_abstracts(papers, papers_sha, pdir / "ref_abstracts.json",
                                                    a.ref_cutoff),
        "citation_graph": lambda: step_citation_graph(papers_path, pdir / "citation-graph.json"),
    }
    failed = 0
    for s in steps:
        try:
            detail = jobs[s]()
            status[s] = {"ok": True, "detail": detail, "at": _now(), "papers_sha256": papers_sha}
            print(f"[profile_tools] {s:18s} ok — {detail}", file=sys.stderr)
        except Exception as e:                                   # noqa: BLE001 — recorded, never swallowed
            failed += 1
            status[s] = {"ok": False, "detail": f"{type(e).__name__}: {e}", "at": _now(), "papers_sha256": papers_sha}
            print(f"[profile_tools] {s:18s} FAILED — {e}", file=sys.stderr)
        _write(status_path, status)
    print(f"[profile_tools] {len(steps) - failed}/{len(steps)} step(s) ok — status in {status_path}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
