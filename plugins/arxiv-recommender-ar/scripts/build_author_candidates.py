#!/usr/bin/env python3
"""arXiv 作者检索 → paper_candidates.json(+ 人读的 .md),喂给 build_profile_papers.py --from-list。

为什么要这个脚本:`--scholar-url` 那条入口受 Google Scholar 每页 100 篇的硬上限约束,而且
Scholar 的条目要反过来解析回 arXiv;`lib/arxiv_client.search_author` 返回的 `_record()` 字段
(arxiv_id / title / abstract / authors / submitted / categories / primary_category)**正好**
是 `--from-list` 需要的全部,`first_date = submitted[:10]` 还直接来自 arXiv 本体(首版日期)。

`au:"Full Name"` 是模糊匹配,一次检索会把同名的人一起带回来。消歧是**机械三步**,不靠模型判断:

  ① 精确名核对   `lib.profile_papers.name_key`(顺序 / 大小写 / 音标 / 标点无关)。
                 `au:` 带回来的、作者表里根本没有这个全名的,直接 not。
  ② 共同作者分量  在①的保留集上建图:两篇论文共享至少一位**本人以外**的作者就连一条边。
                 取包含 anchor 的连通分量 —— 同名的两个人几乎不共享合作者,这条是主力。
  ③ 类目一致性   分量内但主类目不在此人 top-3 archive 里的,标 flag,规则给 peripheral。

规则只**建议** decision(写在每行的 `rule_decision`),文件里的 `decision` 一律留 null;
真正落盘要走 `--emit-set-decisions` 打出来的那条 `set_paper_decisions.py`,由 owner 过目后执行。
**decision 由规则给出 + owner 确认边缘行,不由模型编造。**

用法(插件 venv):
    AR_DATA_ROOT=~/arxiv-proxy/<slug> python scripts/build_author_candidates.py \
        --name "Full Name" [--name "Alt Form"]... [--anchor 2301.01234]... \
        [--max-results 400] [--cache PATH] [--out PATH] [--emit-set-decisions] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_profile_papers import _DECISIONS, _candidates_md  # noqa: E402
from lib import arxiv_client, config  # noqa: E402
from lib import profile_papers as PP  # noqa: E402

TOP_ARCHIVES = 3


def archive(cat: str | None) -> str:
    """`math.OC` → `math`;`cond-mat.mtrl-sci` → `cond-mat`;`quant-ph` → `quant-ph`。"""
    return (cat or "").split(".")[0]


# ────────────────────────── 一、检索 ──────────────────────────

def to_row(rec: dict[str, Any]) -> dict[str, Any]:
    """arxiv_client._record → paper_candidates 行(`--from-list` 读得懂的全部字段)。"""
    first = (rec.get("submitted") or "")[:10] or None
    row = {
        "decision": None, "rule_decision": None, "flags": [],
        "key": None, "arxiv_id": rec.get("arxiv_id"), "paper_id": None,
        "title": rec.get("title") or "", "abstract": rec.get("abstract"),
        "authors": rec.get("authors") or [], "first_date": first,
        "year": int(first[:4]) if first else None,
        "categories": rec.get("categories") or [], "primary_category": rec.get("primary_category"),
        "venue": None, "resolved_by": "arxiv_author", "scholar_citations": None,
    }
    row["key"] = PP.paper_key(row)
    return row


def search(names: list[str], max_results: int,
           cache: Path | None) -> tuple[list[dict[str, Any]], bool]:
    """每个 name form 检索一次,按 arxiv_id 去重。`cache` 命中就不再打 arXiv。

    第二个返回值 `truncated`:某个 name form 恰好取满 `max_results`。`au:` 按投稿日期倒序返回,
    取满就意味着**只拿到了最近的那一截**,T 之前的论文数会被系统性低估 —— 常见名(2026-09-21 实测
    "Qi Liu" / "Jian Tang")必然触发。**截断的候选的计数一律不可信**,筛选层直接判不过。"""
    if cache and cache.exists():
        doc = json.loads(cache.read_text(encoding="utf-8"))
        if doc.get("names") == names and doc.get("max_results") == max_results:
            print(f"[build_author_candidates] cache hit {cache} ({len(doc['rows'])} 行)", file=sys.stderr)
            return doc["rows"], bool(doc.get("truncated"))
    by_id: dict[str, dict[str, Any]] = {}
    truncated = False
    for n in names:
        recs = arxiv_client.search_author(n, max_results)
        truncated = truncated or len(recs) >= max_results
        print(f"[build_author_candidates] au:\"{n}\" → {len(recs)} 篇"
              f"{' (取满,被截断)' if len(recs) >= max_results else ''}", file=sys.stderr)
        for r in recs:
            row = to_row(r)
            if row["arxiv_id"]:
                by_id.setdefault(row["arxiv_id"], row)
    rows = sorted(by_id.values(), key=lambda p: p.get("first_date") or "")
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"names": names, "max_results": max_results, "truncated": truncated,
                                     "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                                     "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    return rows, truncated


# ────────────────────────── 二、机械消歧 ──────────────────────────

def components(rows: list[dict[str, Any]], targets: set[tuple]) -> list[set[str]]:
    """共同作者图的连通分量(节点 = arxiv_id)。本人自己的名字不算边 —— 否则全连成一块。"""
    parent: dict[str, str] = {r["arxiv_id"]: r["arxiv_id"] for r in rows}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    seen: dict[tuple, str] = {}
    for r in rows:
        for a in r["authors"]:
            k = PP.name_key(a)
            if not k or k in targets:
                continue
            if k in seen:
                ra, rb = find(seen[k]), find(r["arxiv_id"])
                if ra != rb:
                    parent[ra] = rb
            else:
                seen[k] = r["arxiv_id"]
    out: dict[str, set[str]] = {}
    for r in rows:
        out.setdefault(find(r["arxiv_id"]), set()).add(r["arxiv_id"])
    return sorted(out.values(), key=len, reverse=True)


def disambiguate(rows: list[dict[str, Any]], names: list[str],
                 anchors: list[str]) -> dict[str, Any]:
    """三步全部就地写进每行的 `rule_decision` / `flags`。返回一份可审计的说明。"""
    targets = {PP.name_key(n) for n in names if PP.name_key(n)}
    # ① 精确名核对
    named = []
    for r in rows:
        if any(PP.name_key(a) in targets for a in r["authors"]):
            named.append(r)
        else:
            r["rule_decision"] = "not"
            r["flags"].append("name_mismatch")
    # ② 共同作者分量
    comps = components(named, targets)
    anchor_set = {a.split("v")[0] for a in anchors}
    chosen: set[str] = set()
    how = "largest_component"
    if anchor_set:
        hit = [c for c in comps if c & anchor_set]
        if hit:
            chosen = set().union(*hit)
            how = f"anchor_components({len(hit)})"
        else:
            how = "anchors_matched_nothing → largest_component"
    if not chosen:
        chosen = comps[0] if comps else set()
    # ③ 类目一致性 —— top-3 archive 从**分量内**的论文派生(不从全集,否则同名者会把自己的领域投进来)
    arch = Counter(archive(r["primary_category"]) for r in named
                   if r["arxiv_id"] in chosen and r["primary_category"])
    top = {a for a, _ in arch.most_common(TOP_ARCHIVES)}
    # 组合判定(owner 2026-09-21 批准)。单独用分量会误杀换过合作者群体的人:2026-09-21 在 4 位
    # 研究者身上实测,分量判死 37 篇,其中 30 篇落在本人 archive 之内 —— Chang 的
    # "Generating Natural Language Adversarial Examples"、Ying Shan 的微软时期工作、
    # Dong 的 "Gaussian Processes on Graphs" 主线,全被当成了别人。跨 archive 的那 7 篇才是真同名。
    for r in named:
        in_comp = r["arxiv_id"] in chosen
        in_arch = archive(r["primary_category"]) in top
        if in_comp and in_arch:
            r["rule_decision"] = "self"
        elif in_comp:                      # 分量内但跨 archive:大合作里的挂名,留记录不进语义通道
            r["rule_decision"] = "peripheral"
            r["flags"].append("off_archive")
        elif in_arch:                      # 分量外但在本人领域内:换了合作者群体,不是别人
            r["rule_decision"] = "self"
            r["flags"].append("component_gap")
        else:                              # 两条都不满足 → 同名者
            r["rule_decision"] = "not"
            r["flags"].append("namesake")
        if not in_comp and len(r["authors"]) <= 1:
            r["flags"].append("solo_no_coauthor_link")
    kept = [r for r in named if r["rule_decision"] != "not"]
    return {
        "n_fetched": len(rows), "n_name_matched": len(named),
        "components": [len(c) for c in comps[:6]], "component_rule": how,
        "anchors": sorted(anchor_set), "top_archives": sorted(top),
        "archive_counts": dict(arch.most_common()),
        "rule_decisions": dict(Counter(r["rule_decision"] for r in rows)),
    }


def _counts(rows: list[dict[str, Any]], cutoff: str, src_from: str, src_to: str) -> dict[str, Any]:
    core = [r for r in rows if r["rule_decision"] != "peripheral"]
    pre = [r for r in core if r["first_date"] and r["first_date"] < cutoff]
    src = [r for r in rows if r["first_date"] and src_from <= r["first_date"] <= src_to]
    return {"n": len(rows), "n_pre_cutoff": len(pre),
            "n_pre_cutoff_with_abstract": sum(1 for r in pre if r["abstract"]),
            "n_sources": len(src)}


def stats(rows: list[dict[str, Any]], cutoff: str, src_from: str, src_to: str,
          audit: dict[str, Any]) -> dict[str, Any]:
    """入选门槛要读的计数,**严格 / 宽松两个口径都给**。

    严格 = 过了共同作者分量那一关(`rule_decision != not`);宽松 = 只过了精确名核对。
    2026-09-21 在研究者身上实测:他 2025 年换合作者群体之后的 8 篇论文与早期论文一个共同作者都不共享,
    分量规则把它们判成了别人 —— 而那 8 篇是 owner 确认过的本人论文。分量规则要靠 owner 给的**跨时代**
    anchor 才准,筛选阶段没有 anchor,所以**门槛按严格口径判(宁可少收人),同时把宽松口径摆出来**。"""
    strict = [r for r in rows if r["rule_decision"] != "not"]
    loose = [r for r in rows if "name_mismatch" not in r["flags"]]
    pre = [r for r in strict if r["rule_decision"] == "self"
           and r["first_date"] and r["first_date"] < cutoff]
    arch = Counter(archive(r["primary_category"]) for r in pre if r["primary_category"])
    cats = Counter(c for r in pre for c in (r["categories"] or []))
    comps = audit.get("components") or [0]
    risk = len(comps) >= 3 and comps[1] / max(comps[0], 1) >= 0.2 if len(comps) > 1 else False
    return {
        "strict": _counts(strict, cutoff, src_from, src_to),
        "loose": _counts(loose, cutoff, src_from, src_to),
        "n_no_date": sum(1 for r in strict if not r["first_date"]),
        "namesake_risk": bool(risk), "component_sizes": comps,
        "primary_archive": arch.most_common(1)[0][0] if arch else None,
        "archive_mix": dict(arch.most_common()),
        "categories_pre_cutoff": dict(cats.most_common(12)),
        "coauthors": sorted({a for r in strict for a in r["authors"]}),
    }


def review_md(doc: dict[str, Any]) -> str:
    """只列需要 owner 过目的边缘行 —— 规则判 not / peripheral / 连不上共同作者图的。"""
    rows = [r for r in doc["papers"] if r["rule_decision"] != "self" or r["flags"]]
    a = doc["disambiguation"]
    out = [f"# 边缘行复核 — {doc['name']}", "",
           f"检索 {a['n_fetched']} 篇 · 精确名核对留下 {a['n_name_matched']} 篇 · "
           f"共同作者分量 {a['components']}(取法:{a['component_rule']})", "",
           "规则只建议;**判 not 的如果其实是本人,请把它挑出来** —— 分量规则在换合作者群体的人身上会误杀。", "",
           "| key | 日期 | 规则判 | flags | 主类目 | 标题 |", "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['key']} | {r.get('first_date') or ''} | {r['rule_decision']} | "
                   f"{','.join(r['flags']) or ''} | {r.get('primary_category') or ''} | "
                   f"{(r.get('title') or '')[:70].replace('|', '/')} |")
    return "\n".join(out) + "\n"


# ────────────────────────── 三、CLI ──────────────────────────

def carry_decisions(rows: list[dict[str, Any]], prior: Path) -> int:
    """把既有候选文件里 owner 已经做过的 `decision` 按 key 搬过来(重建清单时不必重判一遍)。
    搬不到的行留 null —— 由 owner 逐条确认,规则的 `rule_decision` 只是建议,不能顶替确认。"""
    prev = {r.get("key") or r.get("arxiv_id"): r.get("decision")
            for r in json.loads(prior.read_text(encoding="utf-8")).get("papers") or []}
    n = 0
    for r in rows:
        d = prev.get(r["key"]) or prev.get(r["arxiv_id"])
        if d in _DECISIONS:
            r["decision"] = d
            n += 1
    return n


def build(names: list[str], max_results: int, anchors: list[str], cache: Path | None,
          cutoff: str, src_from: str, src_to: str, prior: Path | None = None) -> tuple[dict, dict]:
    rows, truncated = search(names, max_results, cache)
    audit = disambiguate(rows, names, anchors)
    audit["truncated"] = truncated
    audit["decisions_carried"] = carry_decisions(rows, prior) if prior else 0
    doc = {
        "name": names[0], "name_forms": names,
        "source": {"url": f'arXiv au:"{names[0]}"', "tool": "build_author_candidates.py"},
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "disambiguation": audit, "papers": rows,
    }
    return doc, {**audit, **stats(rows, cutoff, src_from, src_to, audit)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--name", action="append", required=True, help="全名,可重复(第一个是主名)")
    ap.add_argument("--anchor", action="append", default=[], help="确定属于此人的 arXiv id,可重复")
    ap.add_argument("--max-results", type=int, default=400)
    ap.add_argument("--cache", type=Path, default=None, help="原始检索结果缓存(命中就不再打 arXiv)")
    ap.add_argument("--out", type=Path, default=None, help="默认 <profile_dir>/paper_candidates.json")
    ap.add_argument("--cutoff", default="2023-07-01")
    ap.add_argument("--source-from", default="2023-09-23", help="来源窗口起(含)")
    ap.add_argument("--source-to", default="2025-01-01", help="来源窗口止(含)")
    ap.add_argument("--carry-decisions", type=Path, default=None,
                    help="既有候选文件:把 owner 已做的 decision 按 key 搬过来")
    ap.add_argument("--emit-set-decisions", action="store_true")
    ap.add_argument("--json", action="store_true", help="把统计打到 stdout")
    args = ap.parse_args()

    config.load_config()
    doc, summary = build(args.name, args.max_results, args.anchor, args.cache,
                         args.cutoff, args.source_from, args.source_to, args.carry_decisions)
    out = args.out or (config.profile_dir() / "paper_candidates.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    out.with_suffix(".md").write_text(_candidates_md(doc), encoding="utf-8")
    out.with_suffix(".review.md").write_text(review_md(doc), encoding="utf-8")
    print(f"[build_author_candidates] {out} · {summary['rule_decisions']} · T 前带摘要 "
          f"{summary['strict']['n_pre_cutoff_with_abstract']}(宽松 {summary['loose']['n_pre_cutoff_with_abstract']})"
          f" · 来源窗口 {summary['strict']['n_sources']}(宽松 {summary['loose']['n_sources']})",
          file=sys.stderr)
    undec = [r for r in doc["papers"] if r["decision"] not in _DECISIONS]
    if undec:
        print(f"[build_author_candidates] {len(undec)} 行没有 decision —— 交 owner 逐条确认:", file=sys.stderr)
        for r in undec[:20]:
            print(f"    {r['key']}  {r.get('first_date')}  规则建议 {r['rule_decision']}  "
                  f"{(r.get('title') or '')[:70]}", file=sys.stderr)
    if args.emit_set_decisions:
        marks = [f'--mark "{r["key"]}={r["rule_decision"]}"' for r in doc["papers"]
                 if r["rule_decision"] in _DECISIONS and r["rule_decision"] != "self"]
        print(f"python scripts/set_paper_decisions.py --candidates {out} \\\n  "
              + " \\\n  ".join(marks) + " \\\n  --rest self")
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
