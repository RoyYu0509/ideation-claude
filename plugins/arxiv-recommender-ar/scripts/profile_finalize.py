#!/usr/bin/env python3
"""Finalize a v3 profile: check the parts, compute what the agent must not write, run the coverage check,
and merge everything into profile.json — only when nothing is missing (2026-09-16).

A profile is built ONCE and must support every recall channel and every ablation variant of it
(report-v2/ablation/PROFILE-SCHEMA.md): building one costs the agent 200–300k tokens, so an ablation must
never have to rebuild it. The builder therefore writes each field to its own file, the deterministic tools
write theirs, and this script merges them — after checking, against lib/channel_spec (the single source of
truth for what every channel × variant needs), that every one of them can be derived.

  data/profile/
    papers.json                     input (build_profile_papers.py)
    parts/paper_notes.json          agent  [{"key", "field", "method", "keywords"}]  one per core paper
    parts/threads.json              agent  [{"name", "summary", "papers"}]
    parts/recent_direction.json     agent  {"recent_direction": "..."}
    parts/keywords_extracted.json   scripts/profile_tools.py
    parts/categories.json           scripts/profile_tools.py
    ref_abstracts.json              scripts/profile_tools.py            (companion, not merged)
    citation-graph.json             scripts/profile_tools.py            (companion, not merged)
    profile.md                      agent — the reranker reads it       (companion, not merged)
    profile_check.json              this script's report (finalize mode always writes it)
    profile.json                    this script's output — written ONLY when every check passes

What this script COMPUTES (never trusts the agent for): each thread's status (active iff a core member's
first version is within profile.active_window_months of as-of), member counts, last date, the schema
version and the `finalized_by` stamp prefetch requires. What it CHECKS: the thread grouping (every recent
core paper in exactly one thread, known keys, no empty thread, thread count within config), the paper notes
(lib/channel_spec.validate_notes: one per core paper, 1–5 keywords each printed in the paper's own title or
abstract), that every tool part exists and was built from THIS papers.json, profile.md's length, and the
coverage table: every channel × variant in lib/channel_spec.VARIANTS is ok, EMPTY (the raw materials are
complete but this researcher's data gives the rule nothing to select) or MISSING. Every MISSING row is an
error, and so is an EMPTY row on a variant production runs; other EMPTY rows are reported as warnings.
Nothing passes silently and nothing falls back to another variant.

  bin/run_py.sh scripts/profile_finalize.py [--as-of YYYY-MM-DD]      finalize (check + merge)
  bin/run_py.sh scripts/profile_finalize.py --check-only [DIR]        read an EXISTING profile.json (any
        version) and print its coverage table; writes nothing; exit 1 if any row blocks
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import channel_spec as CS  # noqa: E402
from lib import config  # noqa: E402
from lib import profile_io as PIO  # noqa: E402
from lib import profile_papers as PP  # noqa: E402

FINALIZER = "profile_finalize.py/2026-09-16-v3"   # stamped into profile.json; prefetch refuses a profile without it
AGENT_PARTS = ("paper_notes", "threads", "recent_direction")
TOOL_PARTS = ("keywords_extracted", "categories")


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def read_parts(pdir: Path) -> tuple[dict[str, Any], list[str]]:
    """parts/*.json → {name: value}; a missing or unreadable part is reported, never defaulted."""
    parts: dict[str, Any] = {}
    problems: list[str] = []
    for name in AGENT_PARTS + TOOL_PARTS:
        f = pdir / "parts" / f"{name}.json"
        if not f.exists():
            who = "the arxiv-profile agent" if name in AGENT_PARTS else "scripts/profile_tools.py"
            problems.append(f"parts/{name}.json is missing (written by {who})")
            continue
        try:
            doc = _load(f)
        except ValueError as e:
            problems.append(f"parts/{name}.json is not valid JSON: {e}")
            continue
        parts[name] = doc.get("recent_direction") if name == "recent_direction" and isinstance(doc, dict) else doc
    return parts, problems


def check_threads(threads: list[dict[str, Any]], papers: list[dict[str, Any]], cfg, as_of: date
                  ) -> tuple[list[str], list[str]]:
    """Validate the agent's grouping and write the computed stats into each thread (in place)."""
    by_key = {PP.paper_key(p): p for p in papers}
    months = cfg.profile_active_window_months
    errors, warnings = [], []
    if not cfg.profile_min_threads <= len(threads) <= cfg.profile_max_threads:
        errors.append(f"{len(threads)} threads — must be between profile.min_threads ({cfg.profile_min_threads}) "
                      f"and profile.max_threads ({cfg.profile_max_threads})")
    assigned: dict[str, list[str]] = {}
    for i, t in enumerate(threads, 1):
        name = t.get("name") or t.get("label")
        if not name:
            errors.append(f"thread #{i} has no name")
            name = f"thread #{i}"
        if not (t.get("summary") or "").strip():
            errors.append(f"thread '{name}' has no summary")
        keys = [str(k) for k in (t.get("papers") or [])]
        unknown = [k for k in keys if k not in by_key]
        if unknown:
            errors.append(f"thread '{name}': unknown paper keys {unknown[:5]} (keys come from papers.json)")
        core = [by_key[k] for k in keys if k in by_key and not by_key[k].get("peripheral")]
        if not core:
            errors.append(f"thread '{name}' has no non-peripheral member paper")
        for k in keys:
            assigned.setdefault(k, []).append(name)
        recent = [p for p in core if PP.is_recent(p, as_of, months)]
        dates = [d for d in (PP.paper_date(p) for p in core) if d]
        years = [int(p["year"]) for p in core if p.get("year")]
        t.update({"n_members": len(core), "n_recent": len(recent),
                  "last_date": max(dates).isoformat() if dates else (str(max(years)) if years else None),
                  "status": "active" if recent else "legacy",
                  "emerging": bool(recent) and len(core) == 1,
                  "n_title_only": sum(1 for p in core if not p.get("abstract")),
                  "keywords": []})          # thread-level phrases retired: agent phrases live in paper_notes
        if core and t["n_title_only"] == len(core):
            warnings.append(f"thread '{name}' has no member paper with an abstract — it gets no semantic channel")
        if t["emerging"]:
            warnings.append(f"thread '{name}' is emerging (one member paper)")
    for k, names in assigned.items():
        if len(names) > 1:
            errors.append(f"paper {k} sits in {len(names)} threads ({names}) — each paper belongs to exactly one")
    missing = [p for p in papers
               if not p.get("peripheral") and PP.is_recent(p, as_of, months) and PP.paper_key(p) not in assigned]
    if missing:
        errors.append(f"{len(missing)} recent paper(s) belong to no thread: "
                      + "; ".join(f"{PP.paper_key(p)} {(p.get('title') or '')[:60]}" for p in missing[:8]))
    return errors, warnings


def finalize(parts: dict[str, Any], papers_doc: dict[str, Any], cfg, as_of: date, *,
             md_text: str | None, papers_sha: str, companions: dict[str, str | None],
             ref_abstracts: dict | None, part_problems: list[str] = ()) -> tuple[dict[str, Any], dict[str, Any]]:
    """Pure core of finalize: parts + papers → (profile.json dict, report). No file I/O."""
    papers = papers_doc.get("papers") or []
    errors: list[str] = list(part_problems)
    warnings: list[str] = []

    for name in TOOL_PARTS:
        doc = parts.get(name)
        if doc is not None and doc.get("papers_sha256") != papers_sha:
            errors.append(f"parts/{name}.json was built from a different papers.json — re-run scripts/profile_tools.py")
    threads = [dict(t) for t in parts.get("threads") or []]
    t_err, t_warn = check_threads(threads, papers, cfg, as_of)
    errors += t_err
    warnings += t_warn
    if md_text is None:
        errors.append("profile.md is missing (written by the arxiv-profile agent)")
    elif len(md_text) > cfg.profile_md_max_chars:
        errors.append(f"profile.md is {len(md_text)} chars — cap is profile.md_max_chars ({cfg.profile_md_max_chars})")
    n_uncertain = sum(1 for p in papers if p.get("date_uncertain"))
    if n_uncertain:
        warnings.append(f"{n_uncertain} paper(s) have no exact first-version date (year only)")

    kp = parts.get("keywords_extracted") or {}
    cats = parts.get("categories") or {}
    final: dict[str, Any] = {
        "schema_version": CS.SCHEMA_V3,
        "finalized_by": FINALIZER,
        "finalized_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "papers_sha256": papers_sha,
        "paper_notes": parts.get("paper_notes") or [],
        "threads": threads,
        "recent_direction": parts.get("recent_direction") or "",
        "keywords": [r["phrase"] for r in kp.get("rows") or []],
        "keywords_source": "extracted" if parts.get("keywords_extracted") is not None else None,
        "keywords_note": kp.get("note"),
        "keywords_pool": kp.get("pool"),
        "arxiv_categories": cats.get("chosen") or [],
        "arxiv_categories_note": cats.get("note"),
    }
    v = CS.view(final, papers, as_of=as_of, companions=companions, ref_abstracts=ref_abstracts,
                params=CS.params_from_config(cfg))
    note_problems = CS.validate_notes(v)
    errors += [f"paper_notes: {p}" for p in note_problems]
    rows = CS.coverage(v, CS.production_variants(cfg))
    errors += [f"coverage {r['id']}: {r['status']} [{r['source']}] {r['missing']}"
               + (" (a variant production runs)" if r["status"] == "EMPTY" else "")
               for r in rows if r["blocking"]]
    warnings += [f"coverage {r['id']}: EMPTY for this researcher [{r['source']}] {r['missing']}"
                 for r in rows if r["status"] == "EMPTY" and not r["blocking"]]

    report: dict[str, Any] = {
        "ok": not errors, "errors": errors, "warnings": warnings, "as_of": as_of.isoformat(),
        "finalizer": FINALIZER, "papers_sha256": papers_sha,
        "threads": [{k: t.get(k) for k in ("name", "status", "n_members", "n_recent", "last_date",
                                           "emerging", "n_title_only")} for t in threads],
        "notes": {"n": len(final["paper_notes"]), "n_core": sum(1 for p in papers if not p.get("peripheral")),
                  "problems": note_problems},
        "categories": {"chosen": final["arxiv_categories"], "note": final["arxiv_categories_note"],
                       "table": cats.get("table")},
        "phrases": kp.get("rows") or [],
        "companions": companions,
        "coverage": rows,
        "md_chars": len(md_text) if md_text is not None else None,
    }
    return final, report


def check_only(pdir: Path, cfg) -> int:
    """Read-only coverage audit of an existing profile directory (any schema version)."""
    try:
        v, prov = PIO.load_view(pdir, cfg)
    except FileNotFoundError as e:
        print(f"[profile_finalize] --check-only: {e}", file=sys.stderr)
        return 1
    production = CS.production_variants(cfg)
    rows = CS.coverage(v, production)
    print(f"profile   {prov['profile_dir']}")
    print(f"schema    {prov['schema']} (schema_version {prov['schema_version']}, finalized_by {prov['finalized_by']!r})")
    print(f"papers    {len(v.papers)} ({len(v.core)} core) · threads {len(v.profile.get('threads') or [])} · "
          f"paper_notes {len(v.profile.get('paper_notes') or [])}")
    print(f"production (config): {sorted(production)}   '*' marks them below\n")
    print(CS.format_table(rows))
    n_block = sum(1 for r in rows if r["blocking"])
    n_empty = sum(1 for r in rows if r["status"] == "EMPTY")
    print(f"\n{sum(r['ok'] for r in rows)}/{len(rows)} channel × variant rows usable · {n_empty} EMPTY for this "
          f"researcher · {n_block} blocking")
    return 1 if n_block else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--as-of", default=None, help="recency anchor (default: papers.json cutoff, else today UTC)")
    ap.add_argument("--check-only", nargs="?", const="", default=None, metavar="DIR",
                    help="audit an existing profile directory (default: this data root's data/profile); writes nothing")
    args = ap.parse_args()
    cfg = config.load_config()

    if args.check_only is not None:
        return check_only(PIO.resolve(args.check_only) if args.check_only else config.profile_dir(), cfg)

    pdir = config.profile_dir()
    papers_path = pdir / "papers.json"
    papers_doc = _load(papers_path)
    papers_sha = _sha256(papers_path)
    as_of_s = args.as_of or papers_doc.get("cutoff") or datetime.now(timezone.utc).date().isoformat()
    parts, part_problems = read_parts(pdir)
    md_path = pdir / "profile.md"
    companions, refs = PIO.load_companions(pdir, papers_sha)
    final, report = finalize(parts, papers_doc, cfg, date.fromisoformat(as_of_s[:10]),
                             md_text=md_path.read_text(encoding="utf-8") if md_path.exists() else None,
                             papers_sha=papers_sha, companions=companions, ref_abstracts=refs,
                             part_problems=part_problems)
    rpath = pdir / "profile_check.json"
    rpath.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for t in report["threads"]:
        print(f"[profile_finalize] {t['status']:6s} members={t['n_members']:>2} recent={t['n_recent']:>2} "
              f"last={t['last_date']}  {t['name']}", file=sys.stderr)
    print(f"[profile_finalize] notes {report['notes']['n']}/{report['notes']['n_core']} core papers · "
          f"categories {report['categories']['chosen']} · {len(report['phrases'])} extracted phrases", file=sys.stderr)
    print("\n" + CS.format_table(report["coverage"]) + "\n", file=sys.stderr)
    for w in report["warnings"]:
        print(f"[profile_finalize] warning: {w}", file=sys.stderr)
    if report["errors"]:
        for e in report["errors"]:
            print(f"[profile_finalize] ERROR: {e}", file=sys.stderr)
        print(f"[profile_finalize] profile.json NOT written; fix the parts and re-run (report: {rpath})", file=sys.stderr)
        return 1
    (pdir / "profile.json").write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[profile_finalize] wrote {pdir / 'profile.json'} (schema_version {CS.SCHEMA_V3}) + {rpath}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
