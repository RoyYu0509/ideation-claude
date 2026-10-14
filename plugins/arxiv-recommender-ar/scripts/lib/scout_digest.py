#!/usr/bin/env python3
"""Render the scout digest from a scout JSON manifest + per-paper ideations.

Reads:
  - data/cache/week-<W>-scout.json        (top_papers list + ideation_manifest)
  - data/ideations/<W>/<arxiv_id>.json    (per-paper ideation, from arxiv-ideate)

Writes:
  - data/digests/<W>-scout.md

Per top paper, renders (all content Chinese except title and arXiv metadata):
  ## <i>. <title>
  arXiv link · authors · categories
  主题: thread_label

  **这篇 paper 做了什么**
  paper_summary (Chinese)

  **与你的研究的关联** ★★★★★
  why_relevant (Chinese, names specific user paper)

  **研究 idea（N 个）**
    1. working_title (Chinese)
       - 核心主张: ...
       - 方法素描: ...
       - 意义: ...
       - 证伪标准: ...

No-ideation case: explains why (quality filter or not run).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import config, ideate_io  # noqa: E402


def render_scout_digest(scout_json_path: Path, digest_path: Path) -> Path:
    with open(scout_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    week = data.get("week", "unknown-week")
    top_papers = data.get("top_papers") or []
    ideations = ideate_io.load_all_ideations(week)
    ledger = _load_ledger(week)

    lines: list[str] = []
    lines.append(f"# arXiv scout digest — {week}\n")
    lines.append(
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}._"
    )
    lines.append("")

    # Research-portfolio breadth overview (M1): every profile thread's best
    # paper this week, decoupled from the deep-dive picks below. Generic over
    # however many threads the profile declares.
    breadth = data.get("breadth")
    if breadth:
        lines.extend(_render_breadth(breadth))

    if not top_papers:
        lines.append("> The scout workflow returned no papers this week.")
        lines.append("")
    else:
        if ledger is not None:
            survived, killed = _ledger_totals(ledger, top_papers)
            lines.append(
                f"{len(top_papers)} 篇论文，{survived} 个 idea 通过验证幸存，"
                f"{killed} 个方向被验证否决。每个幸存 idea 附机器推导的验证摘要，"
                "以及可直接粘贴到 `/research <seed>` 的种子。"
            )
        else:
            total_ideas = sum(len((ideations.get(p["arxiv_id"]) or {}).get("ideas") or [])
                              for p in top_papers)
            lines.append(
                f"{len(top_papers)} 篇论文已排序，{total_ideas} 个机制级别 idea 如下。"
                " 每个 idea 包含核心主张 + 方法素描 + 意义 + 证伪标准"
                " — 将这四个字段组合成一段话即可粘贴到 `/research <seed>`。"
            )
        lines.append("")
        for i, paper in enumerate(top_papers, 1):
            lines.extend(_render_paper(i, paper, ideations, week, ledger))

    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text("\n".join(lines), encoding="utf-8")
    return digest_path


_EXT_TIERS = ["solved", "incremental", "needs_bridge", "natural_followup", "publishable"]


def _ext_rank(v) -> int | None:
    """Tolerant normalize (render-side): legacy int 1-5 OR categorical tier → 1-5."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v) if 1 <= int(v) <= 5 else None
    if isinstance(v, str) and v in _EXT_TIERS:
        return _EXT_TIERS.index(v) + 1
    return None


def _ext_of(p: dict):
    """The paper's extensibility signal: categorical verdict (current) or legacy score."""
    return p.get("extensibility_verdict", p.get("extensibility_score"))


def _stars(ext) -> str:
    n = _ext_rank(ext)
    if n is None:
        return ""
    return "★" * n + "☆" * (5 - n)


def _render_breadth(breadth: list[dict]) -> list[str]:
    """Render the research-portfolio breadth overview. Iterates whatever threads
    the workflow emitted (canonical profile order); no hardcoded thread count."""
    out: list[str] = ["---", "", "## 本周研究版图覆盖速览", ""]
    out.append(
        "_你的每个研究方向本周最相关的一篇（标题 + 一句关联）。"
        "带 ⭑ 的已进入下方深度 ideation；其余为本周该方向的最佳信号，供你快速扫一眼广度。_"
    )
    out.append("")
    for entry in breadth:
        out.append(f"**{entry.get('thread', '?')}**")
        papers = entry.get("papers") or []
        if not papers:
            out.append("- _本周无强相关命中。_")
        for p in papers:
            dd = " ⭑" if p.get("in_deepdive") else ""
            url = f"https://arxiv.org/abs/{p.get('arxiv_id', '')}"
            stars = _stars(_ext_of(p))
            stars_txt = f" {stars}" if stars else ""
            out.append(f"- [{p.get('title', '')}]({url}){dd}{stars_txt}")
            why = (p.get("why_it_matters") or "").strip()
            if why:
                out.append(f"  - {why}")
        out.append("")
    return out


# ── Ledger-aware (verified-kill) render, 2026-07-11 ───────────────────────────
# The ideation ledger (data/cache/week-<W>-ideation-ledger.json) records, per
# paper, the survivor candidate(s) + the graveyard of directions killed WITH
# evidence. RENDER TOLERANT (owner rule): any absent/malformed field degrades to
# less content, never a crash and never a silently dropped paper — when the
# ledger is absent or lacks a paper the plain ideas-list render below stands.

def _load_ledger(week: str) -> dict | None:
    """Read data/cache/week-<W>-ideation-ledger.json; None on absence/parse fail."""
    p = config.cache_dir() / f"week-{week}-ideation-ledger.json"
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("papers"), dict):
        return None
    return data


def _ledger_paper(ledger: dict | None, axid) -> dict | None:
    if not ledger or not axid:
        return None
    lp = (ledger.get("papers") or {}).get(axid)
    return lp if isinstance(lp, dict) else None


def _ledger_totals(ledger: dict, top_papers: list[dict]) -> tuple[int, int]:
    """(survived ideas, killed directions) summed across the shown papers."""
    survived = killed = 0
    for p in top_papers:
        lp = _ledger_paper(ledger, p.get("arxiv_id"))
        if not lp:
            continue
        cands = lp.get("candidates") or {}
        if isinstance(cands, dict):
            survived += sum(1 for c in cands.values()
                            if isinstance(c, dict) and c.get("status") == "converged")
        gy = lp.get("graveyard")
        if isinstance(gy, list):
            killed += len(gy)
    return survived, killed


def _converged_candidates(lp: dict) -> list[dict]:
    """Every converged candidate, in ledger order — refined/<id>-idea<N>.md is the N-th of these
    (arxiv-ideation.js PLAN writes one plan per survivor since 2026-09-12)."""
    cands = lp.get("candidates") or {}
    if not isinstance(cands, dict):
        return []
    return [c for c in cands.values() if isinstance(c, dict) and c.get("status") == "converged"]


def _verification_summary(conv: dict) -> str:
    """One-line 中文 verification summary from a converged candidate, tolerant of
    every absent field (recheck / artifact_pass / refute / deferred_premises)."""
    parts: list[str] = []
    recheck = conv.get("recheck") if isinstance(conv.get("recheck"), dict) else {}
    ap = recheck.get("artifact_pass") if isinstance(recheck.get("artifact_pass"), dict) else {}
    if ap:
        keys = ("prior_art", "premise_probe", "derivation_check", "asset_check")
        passed = sum(1 for k in keys if ap.get(k))
        parts.append(f"{passed}/{len(keys)} 产物通过")
    if recheck.get("all_artifacts_reconfirmed"):
        parts.append("独立复核通过")
    refute = conv.get("refute") if isinstance(conv.get("refute"), dict) else {}
    rv = refute.get("verdict")
    if rv == "clear":
        parts.append("反驳搜索无命中")
    elif rv == "scooped":
        parts.append("反驳搜索命中")
    dp = conv.get("deferred_premises")
    if isinstance(dp, int) and dp > 0:
        parts.append(f"deferred 探针 {dp}")
    return " · ".join(parts)


def _load_survivor_seed(week: str, axid: str, n: int = 0) -> str:
    """The '## /research Seed' block of refined/<id>-idea<n>.md, or '' if absent."""
    p = config.data_dir() / "ideations" / week / "refined" / f"{axid}-idea{n}.md"
    if not p.exists():
        return ""
    try:
        return ideate_io.extract_seed(p.read_text(encoding="utf-8"))
    except OSError:
        return ""


def _render_graveyard(graveyard: list) -> list[str]:
    certs = [g for g in graveyard if isinstance(g, dict)]
    if not certs:
        return []
    out = [f"**☠️ 被验证否决的方向（{len(certs)}）**", ""]
    for g in certs:
        direction = (g.get("direction_zh") or g.get("direction") or "").strip() or "(未命名方向)"
        reason = (g.get("kill_reason") or "?").strip() or "?"
        stage = (g.get("stage") or "?").strip() or "?"
        out.append(f"- {direction} — {reason}@{stage}")
        evidence = (g.get("evidence") or "").strip()
        if evidence:
            if len(evidence) > 160:
                evidence = evidence[:160].rstrip() + "…"
            out.append(f"  - {evidence}")
    out.append("")
    return out


def _render_survivor(conv: dict | None, week: str, axid: str, n: int = 0, total: int = 1) -> list[str]:
    out = ["**✅ 验证幸存 idea**" if total == 1 else f"**✅ 验证幸存 idea {n + 1}/{total}**", ""]
    if isinstance(conv, dict):
        wt = (conv.get("working_title") or "").strip()
        claim = (conv.get("claim") or "").strip()
        if wt:
            out.append(f"**{wt}**")
            out.append("")
        if claim:
            out.append(f"- _核心主张：_ {claim}")
        vsum = _verification_summary(conv)
        if vsum:
            out.append(f"- _验证：_ {vsum}")
        out.append("")
    seed = _load_survivor_seed(week, axid, n)
    if seed:
        out.append("- _粘贴到_ `/research`_：_")
        out.append("")
        out.append("```")
        out.append(seed)
        out.append("```")
        out.append("")
    return out


def _render_ledger_paper(lp: dict, ideation: dict | None,
                         stars_inline: str, week: str, axid: str) -> list[str]:
    """The NEW per-paper layout when the ledger has this paper: summary/relevance
    (from the round-1 ideation JSON when present) + survivor-or-exhaustion block
    + the graveyard of verified-killed directions."""
    out: list[str] = []
    paper_summary = why_relevant = ""
    if isinstance(ideation, dict):
        paper_summary = (ideation.get("paper_summary") or "").strip()
        why_relevant = (ideation.get("why_relevant") or "").strip()
    if paper_summary:
        out.append("**这篇 paper 做了什么**")
        out.append("")
        out.append(paper_summary)
        out.append("")
    out.append(f"**与你的研究的关联**{stars_inline}")
    out.append("")
    if why_relevant:
        out.append(why_relevant)
        out.append("")

    convs = _converged_candidates(lp)
    if convs:
        # every survivor, whatever the paper settled as — a paper that never reached
        # survivor_target (exhausted_budget) still ships the survivors it has
        for n, conv in enumerate(convs):
            out.extend(_render_survivor(conv, week, axid, n, len(convs)))
    else:
        # no survivor at all (exhausted_honest / exhausted_budget): an honest
        # zero, not an error.
        out.append("**⛔ 本周未产出幸存 idea**")
        out.append("")
        note = (lp.get("exhaustion_note_zh") or "").strip()
        if note:
            out.append(note)
            out.append("")

    graveyard = lp.get("graveyard")
    if isinstance(graveyard, list):
        out.extend(_render_graveyard(graveyard))
    return out


def _render_paper(
    n: int,
    paper: dict,
    ideations: dict[str, dict],
    week: str,
    ledger: dict | None = None,
) -> list[str]:
    axid = paper.get("arxiv_id", "?")
    title = paper.get("title", "")
    authors = paper.get("authors") or []
    cats = paper.get("categories") or []
    thread = paper.get("thread", "")
    ext = _ext_of(paper)
    original_rank = paper.get("original_rank")
    ideation = ideations.get(axid)

    stars = _stars(ext)
    stars_inline = f" {stars}" if stars else ""

    out: list[str] = []
    out.append("---")
    out.append("")
    out.append(f"## {n}. {title}")
    out.append("")
    url = f"https://arxiv.org/abs/{axid}"
    rank_suffix = f" · 原始排名 #{original_rank}" if original_rank is not None else ""
    if authors:
        astr = ", ".join(authors[:6]) + (" et al." if len(authors) > 6 else "")
        out.append(f"[arXiv:{axid}]({url}) · _{astr}_ · `{', '.join(cats[:4])}`{rank_suffix}")
    else:
        out.append(f"[arXiv:{axid}]({url})" + (f" · `{', '.join(cats[:4])}`" if cats else "") + rank_suffix)
    if thread:
        out.append(f"**主题：** {thread}")
    out.append("")

    # ── ledger-aware render (verified-kill redesign) ──────────────────────
    # When the ledger knows this paper, render the survivor/graveyard layout
    # INSTEAD of the plain ideas list. Ledger absent or paper unknown → fall
    # through to EXACTLY the pre-redesign behavior below (old weeks unchanged).
    lp = _ledger_paper(ledger, axid)
    if lp is not None:
        out.extend(_render_ledger_paper(lp, ideation, stars_inline, week, axid))
        return out

    # ── no ideation case ──────────────────────────────────────────────────
    # Distinguish 'never written' (not run) from 'on disk but unparseable'
    # (corrupted) — the latter falls back to the intact refined plans so a
    # JSON-level failure never silently erases a paper from the digest.
    if ideation is None:
        out.append(f"**与你的研究的关联**{stars_inline}")
        out.append("")
        score_txt = (
            f"扩展性 {ext}" if isinstance(ext, str)
            else (f"扩展性评分 {ext}/5" if ext is not None else "")
        )
        if ideate_io.find_ideation_file(week, axid) is None:
            out.append(
                f"这篇文章已入选推荐列表（{score_txt}），但 ideation 尚未运行。"
            )
            out.append("")
            return out
        # corrupted ideation JSON — recover from the refined plans on disk
        refined = ideate_io.load_refined_fallback(week, axid)
        if not refined:
            out.append(
                f"这篇文章已入选推荐列表（{score_txt}），但其 ideation 产物损坏（JSON 无法解析），"
                "且无精炼计划可回退。"
            )
            out.append("")
            return out
        out.append(
            "_注：原始 ideation JSON 损坏，以下 idea 来自已完成的精炼计划（refined/）。_"
        )
        out.append("")
        out.append(f"**研究 idea（{len(refined)} 个）**")
        out.append("")
        for i, r in enumerate(refined, 1):
            out.append(f"**{i}. {r.get('working_title') or r.get('source')}**")
            out.append("")
            seed = (r.get("seed") or "").strip()
            if seed:
                out.append(f"- _粘贴到_ `/research`_：_")
                out.append("")
                out.append("```")
                out.append(seed)
                out.append("```")
                out.append("")
        return out

    has_idea = ideation.get("has_journal_level_idea", True)
    paper_summary = (ideation.get("paper_summary") or "").strip()
    why_relevant = (ideation.get("why_relevant") or "").strip()
    ideas = ideation.get("ideas") or []
    notes = (ideation.get("notes") or "").strip()

    # ── no journal-level idea ─────────────────────────────────────────────
    if not has_idea:
        out.append(f"**与你的研究的关联**{stars_inline}")
        out.append("")
        reason = notes or "未提供原因。"
        out.append(f"**这篇文章未能生成可发表质量的 idea。** {reason}")
        out.append("")
        return out

    # ── paper summary (what it does) ──────────────────────────────────────
    if paper_summary:
        out.append("**这篇 paper 做了什么**")
        out.append("")
        out.append(paper_summary)
        out.append("")

    # ── relevance (merged: user-paper link + stars) ───────────────────────
    out.append(f"**与你的研究的关联**{stars_inline}")
    out.append("")
    if why_relevant:
        out.append(why_relevant)
        out.append("")

    # ── research ideas ────────────────────────────────────────────────────
    priority_pick = (ideation.get("priority_pick") or {})
    priority_idx = priority_pick.get("idea_index")

    if ideas:
        out.append(f"**研究 idea（{len(ideas)} 个）**")
        out.append("")
        for i, idea in enumerate(ideas, 1):
            is_priority = (priority_idx is not None and (i - 1) == priority_idx)
            out.extend(_render_idea(i, idea, is_priority=is_priority))

    return out


def _render_idea(
    n: int,
    idea: dict,
    is_priority: bool = False,
) -> list[str]:
    wt = (idea.get("working_title") or "").strip()
    claim = (idea.get("claim") or "").strip()
    method = (idea.get("method_sketch") or "").strip()
    # significance_note replaced thread_connection (decoupled ideation); fall back to the
    # old field so prior-week on-disk JSON still renders.
    sig_note = (idea.get("significance_note") or idea.get("thread_connection") or "").strip()
    falsifier = (idea.get("sharp_falsifier") or "").strip()

    prefix = "**[优先推荐]** " if is_priority else ""
    out: list[str] = []
    out.append(f"{prefix}**{n}. {wt}**")
    out.append("")
    if claim:
        out.append(f"- _核心主张：_ {claim}")
    if method:
        out.append(f"- _方法素描：_ {method}")
    if sig_note:
        out.append(f"- _意义：_ {sig_note}")
    if falsifier:
        out.append(f"- _证伪标准：_ {falsifier}")
    out.append("")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=str, required=True,
                    help="ISO week label, e.g. 2026-W22")
    ap.add_argument("--scout-json", type=Path, default=None,
                    help="Override scout JSON path (default: derived from --week)")
    ap.add_argument("--out", type=Path, default=None,
                    help="Override digest path (default: data/digests/<week>-scout.md)")
    args = ap.parse_args()

    scout_json = args.scout_json or (
        config.cache_dir() / f"week-{args.week}-scout.json"
    )
    if not scout_json.exists():
        print(f"[scout_digest] no scout JSON at {scout_json}", file=sys.stderr)
        return 2

    cfg = config.load_config()
    out = args.out or (
        # data-root-aware (owner principle 2026-07-05): the digest is runtime
        # output — consumers (the JS return contract) read it under the
        # data root, so it must be written there too.
        config.digest_dir(cfg.digest_dir_rel) / f"{args.week}-scout.md"
    )
    render_scout_digest(scout_json, out)
    print(f"[scout_digest] wrote {out}", file=sys.stderr)
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
