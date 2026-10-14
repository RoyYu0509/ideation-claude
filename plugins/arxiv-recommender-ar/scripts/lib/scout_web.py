#!/usr/bin/env python3
"""Generate a self-contained interactive HTML weekly digest.

Reads:
  - data/cache/week-<W>-scout.json        (top_papers list)
  - data/ideations/<W>/<arxiv_id>.json    (per-paper ideation, via ideate_io)
  - data/ideations/<W>/refined/<arxiv_id>-idea<N>.md  (refined plans, optional)

Writes:
  - data/web/<W>-scout.html  (self-contained single-file HTML, auto-opened)
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import config, ideate_io  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


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


def _stars(ext) -> str:
    n = _ext_rank(ext)
    if n is None:
        return ""
    return "★" * n + "☆" * (5 - n)


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def _load_refined(week: str, arxiv_id: str, idea_index: int) -> str | None:
    p = ideate_io.ideation_dir(week) / "refined" / f"{arxiv_id}-idea{idea_index}.md"
    if p.exists():
        return p.read_text(encoding="utf-8")
    # Fallback: JSON-format output from agentic runs that drifted to wrong path/format
    return _load_refined_json(week, arxiv_id, idea_index)


def _load_refined_json(week: str, arxiv_id: str, idea_index: int) -> str | None:
    """Read JSON-format refined file from data/refined/<week>/ (agentic drift fallback).
    Converts to the markdown shape _extract_seed() expects."""
    p = config.data_dir() / "refined" / week / f"{arxiv_id}-idea{idea_index}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

    rs = d.get("research_seed")
    if not rs or not isinstance(rs, dict):
        return None

    # Build seed text from research_seed dict fields
    parts: list[str] = []
    if rs.get("context"):
        parts.append(f"CONTEXT:\n{rs['context']}")
    if rs.get("hypothesis"):
        parts.append(f"HYPOTHESIS:\n{rs['hypothesis']}")
    if rs.get("first_experiment"):
        parts.append(f"FIRST EXPERIMENT:\n{rs['first_experiment']}")
    baselines = rs.get("baselines_to_beat") or []
    if baselines:
        bl_items = baselines if isinstance(baselines, list) else [str(baselines)]
        bl = "\n".join(f"- {b}" for b in bl_items)
        parts.append(f"BASELINES TO BEAT:\n{bl}")
    sc = rs.get("scope_constraints") or {}
    if sc:
        parts.append(
            f"SCOPE CONSTRAINTS:\n"
            f"- Applies to: {sc.get('applies_to', '')}\n"
            f"- Does not apply to: {sc.get('does_not_apply_to', '')}"
        )
    oq = rs.get("open_questions") or []
    if oq:
        qs = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(oq))
        parts.append(f"OPEN QUESTIONS (resolve during proposing phase):\n{qs}")
    seed_text = "\n\n".join(parts)

    # Build minimal plan_body from section scores + key content
    section_labels = ["Significance", "Claim Quality", "Proposition", "Baselines", "Validation"]
    plan_parts: list[str] = [f"**Working title:** {d.get('working_title', '')}"]
    for si in range(5):
        sec = d.get(f"section_{si}")
        if not sec or not isinstance(sec, dict):
            continue
        score = sec.get("score", "?")
        label = section_labels[si]
        key_text = (sec.get("significance_status") or sec.get("revised_claim") or
                    sec.get("proposition") or sec.get("expected_delta") or
                    sec.get("reasoning") or "")
        row = f"**Section {si} — {label}:** {score}/4"
        if key_text:
            row += f"\n\n{str(key_text)[:800]}"
        plan_parts.append(row)
    issues = d.get("priority_issues") or []
    if issues:
        issue_lines = []
        for iss in issues:
            if isinstance(iss, dict):
                issue_lines.append(
                    f"{iss.get('emoji', '•')} **{iss.get('title', '')}**: {iss.get('description', '')}"
                )
            else:
                issue_lines.append(str(iss))
        plan_parts.append("### Priority Issues\n\n" + "\n\n".join(issue_lines))
    plan_body = "\n\n".join(plan_parts)

    return f"{plan_body}\n\n## /research Seed\n\n{seed_text}"


def _extract_seed(refined_md: str) -> tuple[str, str]:
    """Split refined_md at '## /research Seed'.
    Returns (seed_text, plan_body_without_seed).
    """
    marker = "## /research Seed"
    idx = refined_md.find(marker)
    if idx == -1:
        return "", refined_md
    after = refined_md[idx + len(marker):]
    seed_text = after.strip()
    if seed_text.endswith("---"):
        seed_text = seed_text[:-3].rstrip()
    plan_body = refined_md[:idx].rstrip()
    return seed_text, plan_body


# ── Ledger-aware (verified-kill) render, 2026-07-11 ───────────────────────────
# Same spirit as scout_digest.py: the ideation ledger records, per paper, the
# survivor candidate + the graveyard of directions killed WITH evidence. Every
# field is read tolerantly; the ledger being absent or lacking a paper degrades
# to EXACTLY the pre-redesign per-paper render (old weeks unchanged).

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
        lp = _ledger_paper(ledger, p.get("arxiv_id", ""))
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
    """One-line 中文 verification summary, tolerant of every absent field."""
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


def _render_graveyard_html(graveyard: list) -> str:
    """Collapsible (native <details>, no JS) list of verified-killed directions."""
    certs = [g for g in (graveyard or []) if isinstance(g, dict)]
    if not certs:
        return ""
    rows: list[str] = []
    for g in certs:
        direction = _esc((g.get("direction_zh") or g.get("direction") or "").strip() or "(未命名方向)")
        reason = _esc((g.get("kill_reason") or "?").strip() or "?")
        stage = _esc((g.get("stage") or "?").strip() or "?")
        evidence = (g.get("evidence") or "").strip()
        ev_html = ""
        if evidence:
            if len(evidence) > 220:
                evidence = evidence[:220].rstrip() + "…"
            ev_html = f'<div class="grave-ev">{_esc(evidence)}</div>'
        rows.append(
            f'<li class="grave-item"><span class="grave-dir">{direction}</span>'
            f'<span class="grave-tag">{reason}@{stage}</span>{ev_html}</li>'
        )
    return (
        f'<details class="graveyard"><summary>&#9760; 被验证否决的方向（{len(rows)}）</summary>'
        f'<ul class="grave-list">{"".join(rows)}</ul></details>'
    )


def _render_ledger_section(lp: dict, week: str, axid: str) -> tuple[str, str, str, int]:
    """Return (status_badge_html, ideas_html, graveyard_html, survivor_count).

    Survivors → one idea card per converged candidate (reusing _render_idea;
    card N reads refined/<id>-idea<N-1>.md) with its refined plan expandable +
    its /research seed copyable, plus its machine verification summary.
    No survivor → an honest ⛔ exhaustion line. The graveyard collapsible is
    emitted whenever it is non-empty. Every field is read tolerantly."""
    convs = _converged_candidates(lp)
    if convs:
        badge = '<span class="status-badge status-survived">&#9989; 幸存</span>'
        cards = []
        for n, conv in enumerate(convs):
            refined_raw = _load_refined(week, axid, n)
            if refined_raw is not None:
                seed_text, plan_md = _extract_seed(refined_raw)
            else:
                seed_text, plan_md = "", None
            survivor_idea = {
                "working_title": conv.get("working_title") or "",
                "claim": conv.get("claim") or "",
            }
            vsum = _verification_summary(conv)
            vsum_html = f'<p class="paper-body verify-summary">验证：{_esc(vsum)}</p>' if vsum else ""
            cards.append(vsum_html + _render_idea(n + 1, survivor_idea, False, plan_md, seed_text))
        ideas_html = (
            '<div class="section-label">&#9989; 验证幸存 idea</div>'
            + '<div class="ideas-list">'
            + "".join(cards)
            + "</div>"
        )
        survived = len(convs)
    else:
        badge = '<span class="status-badge status-exhausted">&#9940; 枯竭</span>'
        note = _esc((lp.get("exhaustion_note_zh") or "").strip())
        ideas_html = (
            '<div class="section-label">&#9940; 本周未产出幸存 idea</div>'
            + (f'<p class="paper-body">{note}</p>' if note else "")
        )
        survived = 0
    graveyard_html = _render_graveyard_html(lp.get("graveyard"))
    return badge, ideas_html, graveyard_html, survived


# ── per-idea HTML ─────────────────────────────────────────────────────────────

def _render_idea(n: int, idea: dict, is_priority: bool,
                 plan_md: str | None, seed_text: str) -> str:
    wt = _esc((idea.get("working_title") or "").strip())
    claim = _esc((idea.get("claim") or "").strip())
    method = _esc((idea.get("method_sketch") or "").strip())
    # significance_note replaced thread_connection (decoupled ideation, v0.7);
    # fall back to the old field so prior-week JSON still renders.
    sig_note = _esc((idea.get("significance_note") or idea.get("thread_connection") or "").strip())
    falsifier = _esc((idea.get("sharp_falsifier") or "").strip())

    badge = '<span class="badge-priority">&#128204; 优先推荐</span>' if is_priority else ""
    css_class = "idea idea-priority" if is_priority else "idea"

    rows = []
    if claim:
        rows.append(f"<li><strong>核心主张：</strong>{claim}</li>")
    if method:
        rows.append(f"<li><strong>方法素描：</strong>{method}</li>")
    if sig_note:
        rows.append(f"<li><strong>意义：</strong>{sig_note}</li>")
    if falsifier:
        rows.append(f"<li><strong>证伪标准：</strong>{falsifier}</li>")

    expand_btn = '<button class="btn-expand" onclick="toggleOverview(this)">展开 ↓</button>'

    if seed_text:
        enc_seed = _b64(seed_text)
        seed_section = (
            f'<div class="seed-wrap hidden">'
            f'<button class="seed-toggle" onclick="toggleSeed(this)">&#128203; /research 种子 &#9660;</button>'
            f'<div class="seed-content hidden">'
            f'<div class="seed-actions"><button class="seed-copy" onclick="copySeed(this)" data-seed="{enc_seed}">复制种子</button></div>'
            f'<div class="md-body seed-md" data-md="{enc_seed}"></div>'
            f'</div></div>'
        )
    else:
        seed_section = '<p class="no-seed-note hidden">种子尚未生成（此 idea 尚未进入精炼阶段）</p>'

    if plan_md is not None:
        enc_plan = _b64(plan_md)
        detail_div = (f'<div class="idea-detail hidden">'
                      f'<div class="md-body" data-md="{enc_plan}"></div>'
                      f'</div>')
        detail_toggle = ('<button class="detail-toggle hidden" '
                         'onclick="toggleDetail(this)">查看完整分析 ▾</button>')
    else:
        detail_toggle = ""
        detail_div = ""

    bullets = "".join(rows)
    return f"""\
<div class="{css_class}">
  <div class="idea-hd">
    {badge}<span class="idea-num">{n}.</span>
    <span class="idea-wt">{wt}</span>
    {expand_btn}
  </div>
  <ul class="idea-bullets hidden">{bullets}</ul>
  {seed_section}
  {detail_toggle}
  {detail_div}
</div>"""


# ── per-paper HTML ────────────────────────────────────────────────────────────

def _render_paper(idx: int, paper: dict, ideation: dict | None, week: str,
                  ledger: dict | None = None) -> tuple[str, str]:
    """Return (nav_html, content_html)."""
    axid = paper.get("arxiv_id", "?")
    title = paper.get("title") or ""
    authors = paper.get("authors") or []
    cats = paper.get("categories") or []
    thread = paper.get("thread") or ""
    ext = paper.get("extensibility_verdict", paper.get("extensibility_score"))
    stars = _stars(ext)

    ideas: list[dict] = []
    priority_idx: int | None = None
    paper_summary = ""
    why_relevant = ""
    if ideation:
        ideas = ideation.get("ideas") or []
        pp = ideation.get("priority_pick") or {}
        priority_idx = pp.get("idea_index")
        paper_summary = _esc((ideation.get("paper_summary") or "").strip())
        why_relevant = _esc((ideation.get("why_relevant") or "").strip())

    # 'on disk but unparseable' (corrupted) vs 'never written' (not run): the
    # former recovers from the intact refined plans so a JSON failure never
    # silently erases a paper from the report.
    corrupted = ideation is None and ideate_io.find_ideation_file(week, axid) is not None
    refined_fb = ideate_io.load_refined_fallback(week, axid) if corrupted else []

    # ── ledger-driven (verified-kill) section, tolerant of every absent field ──
    # When the ledger knows this paper it OWNS the ideas region (survivor card /
    # exhaustion line) + a status badge + a graveyard collapsible; the raw R1
    # ideas list (which includes killed candidates) is suppressed. Ledger absent
    # or paper unknown → pre-redesign render below (old weeks unchanged).
    lp = _ledger_paper(ledger, axid)
    status_badge = ""
    graveyard_html = ""
    ledger_ideas_html: str | None = None
    if lp is not None:
        status_badge, ledger_ideas_html, graveyard_html, idea_count = \
            _render_ledger_section(lp, week, axid)
    else:
        idea_count = len(ideas)
    nav_title = title[:55] + ("…" if len(title) > 55 else "")

    nav_html = (
        f'<a class="nav-item" href="#paper-{axid}">'
        f'<span class="nav-stars">{stars}</span>'
        f'<span class="nav-title">{_esc(nav_title)}</span>'
        f'<span class="nav-badge">{idea_count}</span>'
        f'</a>'
    )

    astr = _esc(", ".join(authors[:4]) + (" et al." if len(authors) > 4 else ""))
    meta_parts = [
        f'<a href="https://arxiv.org/abs/{axid}" target="_blank" class="arxiv-link">arXiv:{axid}</a>',
    ]
    if astr:
        meta_parts.append(f"<em>{astr}</em>")
    if cats:
        meta_parts.append(f"<code>{_esc(', '.join(cats[:3]))}</code>")
    if paper.get("original_rank") is not None:
        meta_parts.append(f'<span class="orig-rank">原始排名 #{paper.get("original_rank")}</span>')
    meta = " · ".join(meta_parts)

    thread_html = (
        f'<div class="paper-thread">主题：{_esc(thread)}</div>' if thread else ""
    )
    summary_html = (
        f'<div class="section-label">这篇 paper 做了什么</div>'
        f'<p class="paper-body">{paper_summary}</p>'
    ) if paper_summary else ""

    rel_label = f"与你的研究的关联 {stars}" if stars else "与你的研究的关联"
    if why_relevant:
        relevance_html = (
            f'<div class="section-label">{rel_label}</div>'
            f'<p class="paper-body">{why_relevant}</p>'
        )
    elif corrupted:
        note = ("原始 ideation 产物损坏（JSON 无法解析）；以下 idea 来自已完成的精炼计划。"
                if refined_fb else "原始 ideation 产物损坏（JSON 无法解析），且无精炼计划可回退。")
        relevance_html = (
            f'<div class="section-label">{rel_label}</div>'
            f'<p class="paper-body no-plan-note">{_esc(note)}</p>'
        )
    elif lp is not None:
        # ledger paper without a why_relevant line (e.g. honest R1 exhaustion):
        # show only the label — the ✅/⛔ section below carries the honest status.
        relevance_html = f'<div class="section-label">{rel_label}</div>'
    elif ideation is None:
        relevance_html = (
            f'<div class="section-label">{rel_label}</div>'
            f'<p class="paper-body no-plan-note">Ideation 尚未运行。</p>'
        )
    else:
        relevance_html = ""

    ideas_html = ""
    if ledger_ideas_html is not None:
        ideas_html = ledger_ideas_html
    elif ideas:
        ideas_html = '<div class="section-label">研究 ideas</div><div class="ideas-list">'
        for i, idea in enumerate(ideas):
            is_p = (priority_idx is not None and i == priority_idx)
            refined_raw = _load_refined(week, axid, i)
            if refined_raw is not None:
                seed_text, plan_md = _extract_seed(refined_raw)
            else:
                seed_text = ""
                plan_md = None
            ideas_html += _render_idea(i + 1, idea, is_p, plan_md, seed_text)
        ideas_html += "</div>"
    elif refined_fb:
        # corrupted ideation JSON: synthesize idea cards from the refined plans
        # (working title + expandable full plan + copy-able /research seed).
        ideas_html = '<div class="section-label">研究 ideas</div><div class="ideas-list">'
        for i, r in enumerate(refined_fb):
            synth = {"working_title": r.get("working_title") or r.get("source")}
            ideas_html += _render_idea(i + 1, synth, False, r.get("plan_md"), r.get("seed") or "")
        ideas_html += "</div>"

    status_html = f'<div class="paper-status">{status_badge}</div>' if status_badge else ""

    content_html = f"""\
<article class="paper-card" id="paper-{axid}">
  <h2 class="paper-title">{idx}. {_esc(title)}</h2>
  <div class="paper-meta">{meta}</div>
  {status_html}
  {thread_html}
  {summary_html}
  {relevance_html}
  {ideas_html}
  {graveyard_html}
</article>"""

    return nav_html, content_html


# ── CSS / JS ──────────────────────────────────────────────────────────────────

_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
     font-size:15px;line-height:1.65;background:#f8f9fa;color:#212529}
.layout{display:flex;min-height:100vh}
.sidebar{width:270px;min-width:210px;background:#fff;border-right:1px solid #dee2e6;
         position:sticky;top:0;height:100vh;overflow-y:auto;flex-shrink:0;padding:16px 0}
.main{flex:1;padding:32px 40px;max-width:880px}
.header{margin-bottom:28px;border-bottom:2px solid #e9ecef;padding-bottom:18px}
.header h1{font-size:1.45rem;font-weight:700;margin-bottom:4px}
.header .meta{color:#6c757d;font-size:.88rem}
.sidebar-title{font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;
               color:#6c757d;padding:0 16px 8px}
.nav-item{display:flex;flex-direction:column;gap:2px;padding:10px 16px;text-decoration:none;
          color:inherit;border-left:3px solid transparent;transition:background .15s,border-color .15s}
.nav-item:hover{background:#f1f3f5;border-left-color:#adb5bd}
.nav-item.active{border-left-color:#4263eb;background:#edf2ff}
.nav-stars{font-size:.72rem;color:#f08c00}
.nav-title{font-size:.82rem;color:#343a40;line-height:1.4}
.nav-badge{font-size:.72rem;background:#e9ecef;color:#495057;border-radius:10px;
           padding:1px 7px;align-self:flex-start}
.paper-card{background:#fff;border:1px solid #dee2e6;border-radius:10px;
            padding:28px;margin-bottom:28px;scroll-margin-top:20px}
.paper-title{font-size:1.12rem;font-weight:700;margin-bottom:8px}
.paper-meta{font-size:.84rem;color:#6c757d;margin-bottom:6px}
.arxiv-link{color:#4263eb;text-decoration:none}
.arxiv-link:hover{text-decoration:underline}
.paper-thread{font-size:.84rem;color:#6c757d;margin-bottom:12px}
.section-label{font-size:.84rem;font-weight:700;color:#212529;
               margin:20px 0 6px;padding-bottom:5px;border-bottom:1px solid #dee2e6}
.paper-body{font-size:.93rem;color:#495057}
.ideas-list{margin-top:4px}
.idea{border:1px solid #e9ecef;border-radius:8px;margin-bottom:10px;overflow:hidden}
.idea-priority{border-color:#74c0fc;background:#f0f8ff}
.idea-hd{display:flex;align-items:flex-start;gap:8px;padding:12px 14px;flex-wrap:wrap}
.badge-priority{font-size:.75rem;background:#4263eb;color:#fff;border-radius:4px;
                padding:2px 7px;white-space:nowrap}
.idea-num{font-weight:700;color:#495057;flex-shrink:0}
.idea-wt{flex:1;font-weight:600;font-size:.94rem}
.btn-expand{margin-left:auto;font-size:.78rem;background:#4263eb;color:#fff;border:none;
            border-radius:4px;padding:4px 10px;cursor:pointer;white-space:nowrap;
            transition:background .15s;flex-shrink:0}
.btn-expand:hover{background:#3b5bdb}
.btn-expand.open{background:#495057}
.idea-bullets{font-size:.88rem;color:#495057;padding:0 14px 12px 28px}
.idea-bullets li{margin-bottom:4px}
.detail-toggle{display:block;width:100%;text-align:left;font-size:.82rem;font-weight:600;
               background:#edf2ff;color:#3b5bdb;border:none;border-top:1px solid #dbe4ff;
               padding:9px 14px 9px 28px;cursor:pointer;transition:background .15s}
.detail-toggle:hover,.detail-toggle.open{background:#dbe4ff}
.idea-detail{border-top:1px solid #dee2e6;background:#fafafa;padding:20px 24px}
.hidden{display:none}
.idea-detail.hidden{display:none}
.no-plan-note{color:#adb5bd;font-style:italic;font-size:.88rem}
.md-body h1,.md-body h2{margin:1em 0 .5em;font-size:1.05rem;
  border-bottom:1px solid #dee2e6;padding-bottom:4px}
.md-body h3{margin:.8em 0 .3em;font-size:.97rem;color:#343a40}
.md-body p{margin-bottom:.7em;font-size:.92rem}
.md-body ul,.md-body ol{padding-left:1.4em;margin-bottom:.7em}
.md-body li{font-size:.92rem;margin-bottom:.2em}
.md-body code{background:#f1f3f5;padding:1px 5px;border-radius:3px;font-size:.85em}
.md-body pre{background:#f1f3f5;padding:12px;border-radius:6px;overflow-x:auto;margin-bottom:.7em}
.md-body pre code{background:none;padding:0}
.md-body table{border-collapse:collapse;margin-bottom:.7em;width:100%;font-size:.88rem}
.md-body th,.md-body td{border:1px solid #dee2e6;padding:6px 10px;text-align:left}
.md-body th{background:#f1f3f5;font-weight:600}
.md-body blockquote{border-left:3px solid #4263eb;padding-left:12px;color:#6c757d;margin-bottom:.7em}
.md-body a{color:#4263eb}
.md-body hr{border:none;border-top:1px solid #dee2e6;margin:1em 0}
@media(prefers-color-scheme:dark){
  body{background:#1a1b1e;color:#c1c2c5}
  .sidebar{background:#25262b;border-color:#373a40}
  .sidebar-title,.nav-stars{color:#868e96}
  .nav-item:hover{background:#2c2e33}
  .nav-title{color:#c1c2c5}
  .nav-badge{background:#373a40;color:#c1c2c5}
  .paper-card{background:#25262b;border-color:#373a40}
  .paper-title{color:#e9ecef}
  .idea{border-color:#373a40}
  .idea-priority{background:#1c2647;border-color:#4263eb}
  .detail-toggle{background:#1c2647;color:#91a7ff;border-color:#2b3a67}
  .detail-toggle:hover,.detail-toggle.open{background:#2b3a67}
  .idea-detail{background:#2c2e33;border-color:#373a40}
  .section-label{color:#e9ecef;border-color:#373a40}
  .idea-bullets,.paper-body{color:#adb5bd}
  .md-body h1,.md-body h2{border-color:#373a40;color:#e9ecef}
  .md-body h3{color:#c1c2c5}
  .md-body code,.md-body pre{background:#1a1b1e;color:#c1c2c5}
  .md-body th{background:#2c2e33}
  .md-body th,.md-body td{border-color:#373a40}
  .seed-wrap{border-color:#2d4a2d}
  .seed-toggle{background:#1b2d1b;color:#8ce99a}
  .seed-toggle:hover,.seed-toggle.open{background:#1e3a1e}
  .seed-content{background:#192319;border-color:#2d4a2d}
  .seed-copy{background:#2b8a3e}
  .seed-copy:hover{background:#237032}
  .status-survived{background:#152a17;color:#69db7c;border-color:#2b5a2f}
  .status-exhausted{background:#2c2e33;color:#909296;border-color:#373a40}
  .verify-summary{color:#69db7c}
  .graveyard{border-color:#4a2020}
  .graveyard>summary{background:#2a1a1a;color:#ff8787}
  .grave-item{border-color:#373a40}
  .grave-dir{color:#c1c2c5}
  .grave-tag{background:#3a1f1f;color:#ff8787}
  .grave-ev{color:#909296}
}
.seed-wrap{border-top:1px solid #e9ecef}
.seed-toggle{display:block;width:100%;text-align:left;font-size:.82rem;font-weight:600;
             background:#f0fdf4;color:#2f9e44;border:none;padding:9px 14px;
             cursor:pointer;transition:background .15s}
.seed-toggle:hover,.seed-toggle.open{background:#dcfce7}
.seed-content{border-top:1px solid #bbf7d0;background:#f0fdf4;padding:12px 16px 16px}
.seed-actions{display:flex;justify-content:flex-end;margin-bottom:8px}
.seed-copy{font-size:.78rem;background:#2f9e44;color:#fff;border:none;border-radius:4px;
           padding:4px 12px;cursor:pointer;transition:background .15s}
.seed-copy:hover{background:#2b8a3e}
.seed-md{max-height:420px;overflow-y:auto;font-size:.88rem}
.no-seed-note{font-size:.82rem;color:#adb5bd;font-style:italic;
              padding:8px 14px;border-top:1px solid #e9ecef}
/* verified-kill: status badge, verification summary, graveyard (2026-07-11) */
.paper-status{margin:2px 0 8px}
.status-badge{display:inline-block;font-size:.78rem;font-weight:600;border-radius:4px;padding:2px 9px}
.status-survived{background:#ebfbee;color:#2b8a3e;border:1px solid #b2f2bb}
.status-exhausted{background:#f1f3f5;color:#868e96;border:1px solid #dee2e6}
.verify-summary{font-size:.86rem;color:#2f9e44;margin:2px 0 8px}
.graveyard{margin-top:14px;border:1px solid #f1d5d5;border-radius:8px;overflow:hidden}
.graveyard>summary{cursor:pointer;font-size:.84rem;font-weight:600;color:#c92a2a;
                   background:#fff5f5;padding:9px 14px;list-style:none;user-select:none}
.graveyard>summary::-webkit-details-marker{display:none}
.grave-list{list-style:none;padding:8px 14px;margin:0}
.grave-item{padding:6px 0;border-top:1px solid #f1f3f5}
.grave-item:first-child{border-top:none}
.grave-dir{font-weight:600;font-size:.88rem;color:#495057}
.grave-tag{display:inline-block;margin-left:8px;font-size:.76rem;color:#e03131;
           background:#fff0f0;border-radius:4px;padding:1px 7px}
.grave-ev{font-size:.82rem;color:#868e96;margin-top:3px}
"""

_JS = """
// Right-side button: toggle the idea overview (bullets + seed bar).
function toggleOverview(btn) {
  var idea = btn.closest('.idea');
  var bullets = idea.querySelector('.idea-bullets');
  var seedWrap = idea.querySelector('.seed-wrap');
  var noSeedNote = idea.querySelector('.no-seed-note');
  var detailToggle = idea.querySelector('.detail-toggle');
  var detail = idea.querySelector('.idea-detail');
  if (btn.dataset.open !== '1') {
    bullets.classList.remove('hidden');
    if (seedWrap) seedWrap.classList.remove('hidden');
    if (noSeedNote) noSeedNote.classList.remove('hidden');
    if (detailToggle) detailToggle.classList.remove('hidden');
    btn.textContent = '收起 ↑';
    btn.classList.add('open');
    btn.dataset.open = '1';
  } else {
    bullets.classList.add('hidden');
    if (seedWrap) {
      seedWrap.classList.add('hidden');
      var sc = seedWrap.querySelector('.seed-content');
      if (sc) sc.classList.add('hidden');
      var st = seedWrap.querySelector('.seed-toggle');
      if (st) { st.innerHTML = '&#128203; /research 种子 &#9660;'; st.dataset.open = '0'; }
    }
    if (noSeedNote) noSeedNote.classList.add('hidden');
    if (detailToggle) {
      detailToggle.classList.add('hidden');
      detailToggle.textContent = '查看完整分析 ▾';
      detailToggle.classList.remove('open');
      detailToggle.dataset.open = '0';
    }
    if (detail) detail.classList.add('hidden');
    btn.textContent = '展开 ↓';
    btn.classList.remove('open');
    btn.dataset.open = '0';
  }
}
// Seed bar: toggle the /research seed section.
function toggleSeed(btn) {
  var wrap = btn.closest('.seed-wrap');
  var content = wrap.querySelector('.seed-content');
  if (btn.dataset.open !== '1') {
    content.classList.remove('hidden');
    renderMd(content);
    btn.innerHTML = '&#128203; /research 种子 &#9650;';
    btn.dataset.open = '1';
  } else {
    content.classList.add('hidden');
    btn.innerHTML = '&#128203; /research 种子 &#9660;';
    btn.dataset.open = '0';
  }
}
// Copy seed text to clipboard.
function copySeed(btn) {
  var raw = new TextDecoder().decode(
    Uint8Array.from(atob(btn.dataset.seed), function(c) { return c.charCodeAt(0); })
  );
  navigator.clipboard.writeText(raw).then(function() {
    var orig = btn.textContent;
    btn.textContent = '已复制 ✓';
    setTimeout(function() { btn.textContent = orig; }, 1500);
  });
}
// Horizontal bar below seed: toggle the full analysis plan.
function toggleDetail(bar) {
  var idea = bar.closest('.idea');
  var detail = idea.querySelector('.idea-detail');
  if (bar.dataset.open !== '1') {
    detail.classList.remove('hidden');
    renderMd(detail);
    bar.textContent = '收起完整分析 ▴';
    bar.classList.add('open');
    bar.dataset.open = '1';
  } else {
    detail.classList.add('hidden');
    bar.textContent = '查看完整分析 ▾';
    bar.classList.remove('open');
    bar.dataset.open = '0';
  }
}
function renderMd(container) {
  container.querySelectorAll('.md-body[data-md]').forEach(function(el) {
    if (el.dataset.rendered) return;
    var raw = new TextDecoder().decode(
      Uint8Array.from(atob(el.dataset.md), function(c) { return c.charCodeAt(0); })
    );
    if (typeof marked !== 'undefined') {
      el.innerHTML = marked.parse(raw);
    } else {
      var pre = document.createElement('pre');
      pre.style.whiteSpace = 'pre-wrap';
      pre.textContent = raw;
      el.appendChild(pre);
    }
    el.dataset.rendered = '1';
  });
}
var _allCards = document.querySelectorAll('.paper-card');
function _updateNav() {
  if (!_allCards.length) return;
  var activeId = _allCards[0].id;
  for (var i = 0; i < _allCards.length; i++) {
    if (_allCards[i].getBoundingClientRect().top <= 120) activeId = _allCards[i].id;
  }
  if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2) {
    activeId = _allCards[_allCards.length - 1].id;
  }
  document.querySelectorAll('.nav-item').forEach(function(a) {
    a.classList.toggle('active', a.getAttribute('href') === '#' + activeId);
  });
}
window.addEventListener('scroll', _updateNav, { passive: true });
_updateNav();
"""


# ── HTML assembly ─────────────────────────────────────────────────────────────

def generate_html(week: str, top_papers: list[dict], ideations: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ledger = _load_ledger(week)
    total_ideas = sum(
        len((ideations.get(p.get("arxiv_id", "")) or {}).get("ideas") or [])
        for p in top_papers
    )

    nav_items: list[str] = []
    content_items: list[str] = []
    for i, paper in enumerate(top_papers, 1):
        ideation = ideations.get(paper.get("arxiv_id", ""))
        nav_html, content_html = _render_paper(i, paper, ideation, week, ledger)
        nav_items.append(nav_html)
        content_items.append(content_html)

    nav_block = "\n    ".join(nav_items)
    content_block = "\n    ".join(content_items)
    paper_count = len(top_papers)
    if ledger is not None:
        survived, killed = _ledger_totals(ledger, top_papers)
        meta_line = (f'{paper_count} 篇论文 &middot; {survived} 个幸存 idea &middot; '
                     f'{killed} 个否决方向 &middot; 生成于 {ts}')
    else:
        meta_line = f'{paper_count} 篇论文 &middot; {total_ideas} 个 idea &middot; 生成于 {ts}'

    return f"""\
<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>arXiv Scout — {week}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="layout">
  <nav class="sidebar">
    <div class="sidebar-title">论文导航</div>
    {nav_block}
  </nav>
  <div class="main">
    <div class="header">
      <h1>arXiv Scout — {week}</h1>
      <div class="meta">{meta_line}</div>
    </div>
    {content_block}
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/marked@9/marked.min.js"></script>
<script>{_JS}</script>
</body>
</html>
"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate interactive HTML digest from scout week data."
    )
    ap.add_argument("--week", required=True, help="ISO week label, e.g. 2026-W22")
    ap.add_argument("--no-open", dest="auto_open", action="store_false", default=True,
                    help="Skip auto-opening in browser")
    args = ap.parse_args()
    week = args.week

    scout_json_path = config.cache_dir() / f"week-{week}-scout.json"
    if not scout_json_path.exists():
        print(f"[scout_web] no scout JSON at {scout_json_path}", file=sys.stderr)
        return 2

    with open(scout_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    top_papers = data.get("top_papers") or []
    ideations = ideate_io.load_all_ideations(week)

    html = generate_html(week, top_papers, ideations)

    out_path = config.web_dir() / f"{week}-scout.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[scout_web] wrote {out_path}", file=sys.stderr)
    print(str(out_path))

    if args.auto_open:
        try:
            subprocess.run(["open", str(out_path)], check=False, timeout=5)
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
