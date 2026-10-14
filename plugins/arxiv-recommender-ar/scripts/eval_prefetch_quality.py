#!/usr/bin/env python3
"""Evaluate and compare mechanical prefetch systems.

Modes:
  compare       Run multiple systems, compute proxy metrics (dp/kw/tc).
  generate-pool Emit a TREC-style annotation pool for human labeling.
  score-labels  Read an annotated pool, compute NDCG/MRR/Precision + Wilcoxon tests.
  subagent-eval Emit markdown prompt for Claude qualitative evaluation.

Usage examples:
  # 1. Quick proxy-metric comparison
  bash bin/run_py.sh scripts/eval_prefetch_quality.py compare \\
    --candidates data/eval_archive/week-2026-W22-candidates.json \\
    --systems S0,S4

  # 2. Generate annotation pool for human labeling
  bash bin/run_py.sh scripts/eval_prefetch_quality.py generate-pool \\
    --candidates data/eval_archive/week-2026-W22-candidates.json \\
    --systems S0,S4 --pool-k 20 \\
    --out data/eval_archive/week-2026-W22-pool-102316879.md

  # 3. Score labeled pool (after researcher fills in relevance scores)
  bash bin/run_py.sh scripts/eval_prefetch_quality.py score-labels \\
    --candidates data/eval_archive/week-2026-W22-candidates.json \\
    --systems S0,S4 --pool-k 20 \\
    --labels data/eval_archive/week-2026-W22-pool-102316879.md

  # 4. Generate Claude subagent eval prompt
  bash bin/run_py.sh scripts/eval_prefetch_quality.py subagent-eval \\
    --candidates data/eval_archive/week-2026-W22-candidates.json \\
    --compare S0,S4 --subagent-k 10
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config  # noqa: E402

# ── Domain / proxy metric signals ─────────────────────────────────────────────

_DOMAIN_CATS = {
    "cond-mat.mtrl-sci", "physics.comp-ph", "math.NA",
    "physics.chem-ph", "math-ph", "physics.flu-dyn",
    "physics.atom-ph", "cond-mat.dis-nn", "cs.CE",
}
_SPEC_KWS = {
    "quasicontinuum", "atomistic", "dislocation", "interatomic",
    "mace", "multiscale", "microstructure", "phase-field",
    "pinn", "physics-informed", "allen-cahn", "crystalline", "mlip",
    "machine-learned", "continuum coupling",
}

SYSTEMS: dict[str, dict] = {
    "S0": {"label": "Baseline",      "signals": ""},
    "S1": {"label": "+PRF",          "signals": "prf"},
    "S2": {"label": "+Thread",       "signals": "thread"},
    "S3": {"label": "+CatReb",       "signals": "cat-rebalance"},
    "S4": {"label": "PRF+Thread",    "signals": "prf,thread"},
    "S5": {"label": "Cocktail-A",    "signals": "prf,thread,cat-rebalance"},
}

_KS_CACHE: list[int] | None = None


def _ks() -> list[int]:
    """Recall/NDCG cutoffs from config.yaml (eval.k_values); loaded once."""
    global _KS_CACHE
    if _KS_CACHE is None:
        _KS_CACHE = list(config.load_config().eval_block["k_values"])
    return _KS_CACHE

# ── IR metric functions ────────────────────────────────────────────────────────

def dcg_at_k(gains: list[float], k: int) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains[:k]))


def ndcg_at_k(
    ranked_axids: list[str],
    labels: dict[str, int],
    k: int,
    gain_fn=lambda r: 2**r - 1,
) -> float:
    gains = [gain_fn(labels.get(axid, 0)) for axid in ranked_axids[:k]]
    ideal = sorted([gain_fn(v) for v in labels.values()], reverse=True)
    idcg = dcg_at_k(ideal, k)
    return dcg_at_k(gains, k) / idcg if idcg > 0 else 0.0


def mrr(ranked_axids: list[str], labels: dict[str, int], threshold: int = 2) -> float:
    for i, axid in enumerate(ranked_axids):
        if labels.get(axid, 0) >= threshold:
            return 1.0 / (i + 1)
    return 0.0


def precision_at_k(
    ranked_axids: list[str], labels: dict[str, int], k: int, threshold: int = 2
) -> float:
    top = ranked_axids[:k]
    return sum(1 for a in top if labels.get(a, 0) >= threshold) / k if top else 0.0


# ── Proxy metrics (no human labels) ───────────────────────────────────────────

def _has_domain_cat(c: dict) -> bool:
    return any(cat in _DOMAIN_CATS for cat in c.get("categories", []))


def _has_spec_kw(c: dict) -> bool:
    text = f"{c.get('title','')} {c.get('abstract','')}".lower()
    return any(kw in text for kw in _SPEC_KWS)


def _load_thread_kws(profile_json_path: Path) -> list[tuple[str, set[str]]]:
    if not profile_json_path.exists():
        return []
    with open(profile_json_path) as f:
        p = json.load(f)
    return [
        (t.get("label", "?"), {k.lower() for k in (t.get("keywords") or [])})
        for t in p.get("threads", [])
        if t.get("keywords")
    ]


def _thread_hits(c: dict, thread_kws: list[tuple[str, set[str]]]) -> set[str]:
    text = f"{c.get('title','')} {c.get('abstract','')}".lower()
    return {label for label, kws in thread_kws if any(k in text for k in kws)}


def compute_proxy_metrics(
    candidates: list[dict],
    thread_kws: list[tuple[str, set[str]]],
) -> dict[str, dict[int, float]]:
    res: dict[str, dict[int, float]] = {"dp": {}, "kw": {}, "tc": {}}
    for k in _ks():
        top = candidates[:k]
        if not top:
            res["dp"][k] = res["kw"][k] = res["tc"][k] = 0.0
            continue
        res["dp"][k] = sum(_has_domain_cat(c) for c in top) / k
        res["kw"][k] = sum(_has_spec_kw(c) for c in top) / k
        covered: set[str] = set()
        for c in top:
            covered |= _thread_hits(c, thread_kws)
        res["tc"][k] = float(len(covered))
    return res


# ── Prefetch runner ────────────────────────────────────────────────────────────

def run_prefetch(
    candidates_path: Path,
    signals: str,
    top_k: int,
    run_py: str,
    prefetch_script: Path,
    out_path: Path,
    profile_dir: Path | None = None,
) -> list[dict]:
    cmd = [
        run_py, str(prefetch_script),
        "--candidates", str(candidates_path),
        "--top-k", str(top_k),
        "--out", str(out_path),
    ]
    # Always pass --signals to prevent config leakage (empty string = baseline, no cocktail)
    cmd += ["--signals", signals]
    if profile_dir:
        cmd += [
            "--profile-json", str(profile_dir / "profile.json"),
            "--profile-papers", str(profile_dir / "papers.json"),
        ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [stderr] {result.stderr.strip()[:400]}", file=sys.stderr)
        raise RuntimeError(f"prefetch failed (rc={result.returncode})")
    for line in result.stderr.splitlines():
        print(f"    {line}", file=sys.stderr)
    with open(out_path) as f:
        return json.load(f)["candidates"]


# ── Pool generation ────────────────────────────────────────────────────────────

def generate_pool_markdown(
    candidates_by_system: dict[str, list[dict]],
    pool_k: int,
    week: str,
    author_id: str,
    profile_json_path: Path,
) -> str:
    # TREC-style pooling: union of top-pool_k from each system, shuffled
    pool: dict[str, dict] = {}
    for sys_id, cands in candidates_by_system.items():
        for c in cands[:pool_k]:
            axid = c["arxiv_id"]
            if axid not in pool:
                pool[axid] = c

    pool_list = list(pool.values())
    random.shuffle(pool_list)

    # Insert 2 bait papers (sanity check for annotator)
    bait_axids: set[str] = set()
    if len(pool_list) >= 5:
        # Take 2 low-ranked papers from S0 as bait (likely irrelevant)
        s0_cands = candidates_by_system.get("S0", [])
        for c in reversed(s0_cands[-10:]):
            if c["arxiv_id"] not in pool:
                pool_list.insert(random.randint(len(pool_list)//2, len(pool_list)), c)
                bait_axids.add(c["arxiv_id"])
            if len(bait_axids) >= 2:
                break

    # Load thread labels for the annotation hint
    thread_labels: list[str] = []
    if profile_json_path.exists():
        with open(profile_json_path) as f:
            pj = json.load(f)
        thread_labels = [t.get("label", "") for t in pj.get("threads", [])]

    threads_hint = "\n".join(f"  - {t}" for t in thread_labels)

    lines = [
        f"---",
        f"week: {week}",
        f"author_id: {author_id}",
        f"systems: {','.join(sorted(candidates_by_system.keys()))}",
        f"pool_k: {pool_k}",
        f"total_pool: {len(pool_list)}",
        f"generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"---",
        f"",
        f"# Annotation Pool — Week {week}",
        f"",
        f"Rate each paper **0–3**:",
        f"- **3** High relevance: directly extends a specific thread sub-problem",
        f"- **2** Relevant: clearly fits a thread, worth reading",
        f"- **1** Marginal: adjacent field, possible inspiration",
        f"- **0** Not relevant",
        f"",
        f"Your research threads (for reference when filling Thread field):",
        threads_hint,
        f"",
        f"Fill in `Relevance` and (for score ≥1) `Thread` fields below.",
        f"",
        f"---",
        f"",
    ]

    for i, c in enumerate(pool_list, 1):
        axid = c["arxiv_id"]
        bait_note = "  <!-- BAIT — sanity check, expected low relevance -->" if axid in bait_axids else ""
        abstract_snippet = (c.get("abstract") or "")[:400].replace("\n", " ")
        cats = ", ".join((c.get("categories") or [])[:3])
        lines += [
            f"### P{i:02d}  <!-- {axid} -->{bait_note}",
            f"**Title:** {c.get('title','')}  ",
            f"**arXiv:** {axid} | **Categories:** {cats}  ",
            f"**Abstract:** {abstract_snippet}...",
            f"",
            f"**Relevance (0-3):** ___  ",
            f"**Thread (if ≥1):** ___",
            f"",
            f"---",
            f"",
        ]

    return "\n".join(lines)


# ── Label parsing ──────────────────────────────────────────────────────────────

def parse_pool_labels(pool_path: Path) -> tuple[dict[str, int], str, str]:
    """Parse annotated pool markdown.
    Returns: (labels {arxiv_id: score}, week, author_id).
    """
    text = pool_path.read_text()

    # Extract metadata
    week = re.search(r"^week:\s*(\S+)", text, re.MULTILINE)
    author_id = re.search(r"^author_id:\s*(\S+)", text, re.MULTILINE)
    week = week.group(1) if week else "unknown"
    author_id = author_id.group(1) if author_id else "unknown"

    # Find all P## blocks: extract arxiv_id and relevance score
    block_pattern = re.compile(
        r"### P\d+\s+<!--\s*(\S+)\s*-->.*?\*\*Relevance \(0-3\):\*\*\s*([0-3])",
        re.DOTALL,
    )
    labels: dict[str, int] = {}
    for m in block_pattern.finditer(text):
        axid = m.group(1)
        score = int(m.group(2))
        labels[axid] = score

    return labels, week, author_id


# ── Statistical tests ──────────────────────────────────────────────────────────

def wilcoxon_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """Return (statistic, p-value). Falls back to NaN if n < 5."""
    try:
        from scipy.stats import wilcoxon as _wilcoxon
        if len(a) < 5:
            return float("nan"), float("nan")
        stat, p = _wilcoxon(a, b, alternative="two-sided")
        return float(stat), float(p)
    except ImportError:
        return float("nan"), float("nan")


def cohens_d(a: list[float], b: list[float]) -> float:
    import math
    if len(a) < 2:
        return float("nan")
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    var_a = sum((x - mean_a) ** 2 for x in a) / (len(a) - 1)
    var_b = sum((x - mean_b) ** 2 for x in b) / (len(b) - 1)
    pooled_std = math.sqrt((var_a + var_b) / 2)
    return (mean_b - mean_a) / pooled_std if pooled_std > 0 else float("nan")


# ── Subagent eval prompt ───────────────────────────────────────────────────────

def _subagent_prompt(
    profile_md: str,
    threads_summary: str,
    group_a: list[dict],
    group_b: list[dict],
) -> str:
    def fmt_papers(papers: list[dict]) -> str:
        lines = []
        for i, p in enumerate(papers, 1):
            abstract = (p.get("abstract") or "")[:350]
            cats = ", ".join((p.get("categories") or [])[:3])
            lines += [
                f"**{i}. {p.get('title','[no title]')}**",
                f"   Categories: {cats}",
                f"   Abstract: {abstract}...",
                "",
            ]
        return "\n".join(lines)

    return f"""# Blind Recommendation Quality Evaluation

You are evaluating two ranked lists of academic papers against a researcher profile.
Evaluate each paper independently — do not reveal source system.

## Researcher Profile (excerpt)

{profile_md[:2000]}

## Research Threads
{threads_summary}

---

## Group A (top-{len(group_a)} papers)

{fmt_papers(group_a)}

---

## Group B (top-{len(group_b)} papers)

{fmt_papers(group_b)}

---

## Your Task

For **each paper in Group A and Group B**:
1. Rate relevance **1–5** (5=directly extends a thread sub-problem; 1=unrelated)
2. One sentence: name the specific thread or "none"

Then:
- **mean_A**, **mean_B**: mean scores
- **thread_coverage_A/B**: distinct threads represented (0–{len(threads_summary.splitlines())})
- **verdict**: which group is better and why (2–3 sentences)

Output as JSON:
```json
{{
  "scores_A": [{{"title":"...", "score":3, "reason":"..."}}],
  "scores_B": [{{"title":"...", "score":3, "reason":"..."}}],
  "mean_A": 3.2,
  "mean_B": 3.8,
  "thread_coverage_A": 3,
  "thread_coverage_B": 4,
  "verdict": "..."
}}
```
"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def _common_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--systems", default=None, help="default: config eval.mechanical.systems")
    ap.add_argument("--top-k", type=int, default=None,
                    help="default: config eval.mechanical.top_k or scout.prefetch_top_k")
    ap.add_argument("--author", default=None,
                    help="S2 author ID for multi-researcher eval (uses data/users/<id>/profile/)")


def _resolve_profile_dir(author: str | None) -> Path:
    return config.profile_dir_for(author)


def _resolve_thread_kws(profile_dir: Path) -> list[tuple[str, set[str]]]:
    return _load_thread_kws(profile_dir / "profile.json")


def cmd_compare(args: argparse.Namespace) -> int:
    profile_dir = _resolve_profile_dir(args.author)
    thread_kws = _resolve_thread_kws(profile_dir)
    plugin_root = config.data_root()  # runtime-folder principle (2026-07-05): eval artifacts live under the data root, never the plugin dir
    run_py = str(plugin_root / "bin" / "run_py.sh")
    prefetch_script = plugin_root / "scripts" / "prefetch.py"
    systems = [s.strip() for s in args.systems.split(",")]

    results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        for sid in systems:
            if sid not in SYSTEMS:
                print(f"Unknown system {sid}, skipping", file=sys.stderr)
                continue
            defn = SYSTEMS[sid]
            out_path = Path(tmpdir) / f"{sid}.json"
            print(f"\nRunning {sid} ({defn['label']})...", file=sys.stderr)
            cands = run_prefetch(
                args.candidates, defn["signals"], args.top_k,
                run_py, prefetch_script, out_path, profile_dir,
            )
            metrics = compute_proxy_metrics(cands, thread_kws)
            results[sid] = {"metrics": metrics, "candidates": cands, "label": defn["label"]}

    if not results:
        print("No systems ran."); return 1

    print("\n" + "=" * 72)
    print("PREFETCH COMPARISON (proxy metrics — no human labels)")
    print("=" * 72)
    for metric, name in [("dp", "Domain Precision"), ("kw", "Keyword Hit"), ("tc", "Thread Coverage (0-6)")]:
        print(f"\n{name} @ k:")
        hdr = f"{'System':<18} " + " ".join(f"k={k:<5}" for k in _ks())
        print(hdr); print("-" * len(hdr))
        for sid in systems:
            if sid not in results: continue
            row = results[sid]
            label = f"{sid}:{row['label']}"[:17]
            vals = [
                f"{row['metrics'][metric].get(k, 0):.2f} " if metric != "tc"
                else f"{row['metrics'][metric].get(k, 0):.0f}    "
                for k in _ks()
            ]
            print(f"{label:<18} " + " ".join(f"{v:<6}" for v in vals))

    if "S0" in results:
        print("\nDELTA dp@10 vs S0:")
        base = results["S0"]["metrics"]["dp"].get(10, 0)
        for sid in systems:
            if sid == "S0" or sid not in results: continue
            d = results[sid]["metrics"]["dp"].get(10, 0) - base
            print(f"  {sid} ({results[sid]['label']}): {d:+.3f}")
    return 0


def cmd_generate_pool(args: argparse.Namespace) -> int:
    profile_dir = _resolve_profile_dir(args.author)
    plugin_root = config.data_root()  # runtime-folder principle (2026-07-05): eval artifacts live under the data root, never the plugin dir
    run_py = str(plugin_root / "bin" / "run_py.sh")
    prefetch_script = plugin_root / "scripts" / "prefetch.py"
    systems = [s.strip() for s in args.systems.split(",")]

    with open(args.candidates) as f:
        cand_data = json.load(f)
    week = cand_data.get("week", "unknown")
    author_id = args.author or config.load_config().s2_author_id

    cands_by_sys: dict[str, list[dict]] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        for sid in systems:
            if sid not in SYSTEMS: continue
            defn = SYSTEMS[sid]
            out_path = Path(tmpdir) / f"{sid}.json"
            print(f"Running {sid}...", file=sys.stderr)
            cands_by_sys[sid] = run_prefetch(
                args.candidates, defn["signals"], args.pool_k,
                run_py, prefetch_script, out_path, profile_dir,
            )

    md = generate_pool_markdown(
        cands_by_sys,
        pool_k=args.pool_k,
        week=week,
        author_id=author_id,
        profile_json_path=profile_dir / "profile.json",
    )
    out = args.out or (config.eval_archive_dir() / f"week-{week}-pool-{author_id}.md")
    Path(out).write_text(md)
    print(f"Pool written to: {out}")
    print(f"  {len([l for l in md.splitlines() if l.startswith('### P')])} papers to annotate")
    print(f"  Fill in 'Relevance (0-3)' and 'Thread' fields, then run score-labels.")
    return 0


def cmd_score_labels(args: argparse.Namespace) -> int:
    profile_dir = _resolve_profile_dir(args.author)
    plugin_root = config.data_root()  # runtime-folder principle (2026-07-05): eval artifacts live under the data root, never the plugin dir
    run_py = str(plugin_root / "bin" / "run_py.sh")
    prefetch_script = plugin_root / "scripts" / "prefetch.py"
    systems = [s.strip() for s in args.systems.split(",")]

    labels, week, author_id = parse_pool_labels(args.labels)
    if not labels:
        print("No labels found in pool file. Have you filled in the Relevance fields?")
        return 1
    print(f"Loaded {len(labels)} labels (week={week}, author={author_id})", file=sys.stderr)

    labeled_count = sum(1 for v in labels.values() if v >= 0)
    relevant_count = sum(1 for v in labels.values() if v >= 2)
    print(f"  {labeled_count} papers labeled, {relevant_count} relevant (score≥2)", file=sys.stderr)

    ranked: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        for sid in systems:
            if sid not in SYSTEMS: continue
            defn = SYSTEMS[sid]
            out_path = Path(tmpdir) / f"{sid}.json"
            print(f"Running {sid}...", file=sys.stderr)
            cands = run_prefetch(
                args.candidates, defn["signals"], args.pool_k,
                run_py, prefetch_script, out_path, profile_dir,
            )
            ranked[sid] = [c["arxiv_id"] for c in cands]

    ks_eval = [k for k in _ks() if k <= args.pool_k]
    print("\n" + "=" * 72)
    print("IR METRICS (with human labels)")
    print("=" * 72)

    all_ndcg: dict[str, list[float]] = defaultdict(list)
    for k in ks_eval:
        print(f"\n--- k={k} ---")
        print(f"{'System':<18} {'NDCG@k':>8} {'MRR':>8} {'P@k(≥2)':>10} {'P@k(≥1)':>10}")
        print("-" * 60)
        for sid in systems:
            if sid not in ranked: continue
            label = f"{sid}:{SYSTEMS[sid]['label']}"[:17]
            ndcg = ndcg_at_k(ranked[sid], labels, k)
            m = mrr(ranked[sid], labels, threshold=2)
            p2 = precision_at_k(ranked[sid], labels, k, threshold=2)
            p1 = precision_at_k(ranked[sid], labels, k, threshold=1)
            all_ndcg[sid].append(ndcg)
            print(f"{label:<18} {ndcg:>8.3f} {m:>8.3f} {p2:>10.3f} {p1:>10.3f}")

    # Statistical tests at k=10 if multiple weeks' data were provided
    # (single week: just report values, can't do significance test)
    if "S0" in ranked and len(ks_eval) >= 1:
        k_main = 10 if 10 in ks_eval else ks_eval[-1]
        ndcg_s0 = ndcg_at_k(ranked.get("S0", []), labels, k_main)
        print(f"\nNDCG@{k_main} comparison (single week — add more weeks for significance):")
        for sid in systems:
            if sid == "S0" or sid not in ranked: continue
            ndcg_sid = ndcg_at_k(ranked[sid], labels, k_main)
            delta = ndcg_sid - ndcg_s0
            print(f"  {sid} ({SYSTEMS[sid]['label']}): NDCG@{k_main}={ndcg_sid:.3f} (Δ={delta:+.3f} vs S0)")

    # Save results JSON for multi-week aggregation
    out_json = config.eval_archive_dir() / f"week-{week}-scores-{author_id}.json"
    scores_out = {
        "week": week,
        "author_id": author_id,
        "label_stats": {"total": labeled_count, "relevant_2plus": relevant_count},
        "systems": {},
    }
    for k in ks_eval:
        for sid in systems:
            if sid not in ranked: continue
            if sid not in scores_out["systems"]:
                scores_out["systems"][sid] = {}
            scores_out["systems"][sid][f"ndcg@{k}"] = ndcg_at_k(ranked[sid], labels, k)
            scores_out["systems"][sid][f"mrr"] = mrr(ranked[sid], labels)
            scores_out["systems"][sid][f"p@{k}_strict"] = precision_at_k(ranked[sid], labels, k, 2)
    with open(out_json, "w") as f:
        json.dump(scores_out, f, indent=2)
    print(f"\nScores saved to: {out_json}")
    return 0


def cmd_aggregate(args: argparse.Namespace) -> int:
    """Aggregate multi-week scores and run significance tests."""
    archive_dir = config.eval_archive_dir()
    author_id = args.author or config.load_config().s2_author_id
    score_files = sorted(archive_dir.glob(f"week-*-scores-{author_id}.json"))
    if not score_files:
        print(f"No score files found for author {author_id} in {archive_dir}")
        return 1

    all_data: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    weeks_found = []
    for f in score_files:
        with open(f) as fh:
            d = json.load(fh)
        weeks_found.append(d["week"])
        for sid, metrics in d.get("systems", {}).items():
            for mname, val in metrics.items():
                all_data[sid][mname].append(val)

    print(f"\n{'='*72}")
    print(f"MULTI-WEEK AGGREGATION ({len(weeks_found)} weeks: {', '.join(weeks_found)})")
    print(f"Author: {author_id}")
    print(f"{'='*72}")

    k_main = 10
    metric_main = f"ndcg@{k_main}"
    systems_found = sorted(all_data.keys())

    print(f"\nNDCG@{k_main} per week + aggregate:")
    print(f"{'System':<18} " + " ".join(f"W{i+1:02d}   " for i in range(len(weeks_found)))
          + f" {'Mean':>7} {'±Std':>7}")
    print("-" * (18 + 9 * len(weeks_found) + 16))

    for sid in systems_found:
        vals = all_data[sid].get(metric_main, [])
        mean = sum(vals) / len(vals) if vals else 0
        std = (sum((v - mean)**2 for v in vals) / max(len(vals)-1, 1))**0.5
        vals_str = " ".join(f"{v:.3f} " for v in vals)
        print(f"{sid:<18} {vals_str} {mean:>7.3f} {std:>7.3f}")

    # Wilcoxon tests vs S0
    if "S0" in all_data:
        s0_vals = all_data["S0"].get(metric_main, [])
        print(f"\nWilcoxon signed-rank test vs S0 at NDCG@{k_main} (n={len(s0_vals)}):")
        for sid in systems_found:
            if sid == "S0": continue
            sid_vals = all_data[sid].get(metric_main, [])
            if len(sid_vals) != len(s0_vals): continue
            stat, p = wilcoxon_test(s0_vals, sid_vals)
            d = cohens_d(s0_vals, sid_vals)
            s0_mean = sum(s0_vals)/len(s0_vals)
            sid_mean = sum(sid_vals)/len(sid_vals)
            note = "**p<0.05**" if p < 0.05 else ("p<0.10" if p < 0.10 else "n.s.")
            print(f"  {sid}: {s0_mean:.3f} → {sid_mean:.3f}  "
                  f"p={p:.3f} {note}  d={d:.2f}  (n={len(s0_vals)} weeks)")
    return 0


def cmd_subagent_eval(args: argparse.Namespace) -> int:
    profile_dir = _resolve_profile_dir(args.author)
    plugin_root = config.data_root()  # runtime-folder principle (2026-07-05): eval artifacts live under the data root, never the plugin dir
    run_py = str(plugin_root / "bin" / "run_py.sh")
    prefetch_script = plugin_root / "scripts" / "prefetch.py"

    pair = [s.strip() for s in args.compare.split(",")]
    if len(pair) != 2 or not all(p in SYSTEMS for p in pair):
        print(f"--compare must be two valid system IDs, e.g. S0,S4"); return 1

    sid_a, sid_b = pair
    cands_pair: dict[str, list[dict]] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        for sid in pair:
            out_path = Path(tmpdir) / f"{sid}.json"
            print(f"Running {sid}...", file=sys.stderr)
            cands_pair[sid] = run_prefetch(
                args.candidates, SYSTEMS[sid]["signals"], args.top_k,
                run_py, prefetch_script, out_path, profile_dir,
            )

    profile_md_path = profile_dir / "profile.md"
    profile_json_path = profile_dir / "profile.json"
    profile_md = profile_md_path.read_text() if profile_md_path.exists() else ""
    threads_summary = ""
    if profile_json_path.exists():
        with open(profile_json_path) as f:
            pj = json.load(f)
        threads_summary = "\n".join(
            f"- **{t['label']}**: {t.get('summary','')[:100]}"
            for t in pj.get("threads", [])
        )

    prompt = _subagent_prompt(
        profile_md, threads_summary,
        cands_pair[sid_a][:args.subagent_k],
        cands_pair[sid_b][:args.subagent_k],
    )
    with open(args.candidates) as f:
        week = json.load(f).get("week", "unknown")
    author_id = args.author or config.load_config().s2_author_id
    out = config.eval_dir() / f"eval_{sid_a}_vs_{sid_b}_{week}_{author_id}.md"
    out.write_text(prompt)
    print(f"Subagent eval prompt written to: {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    # compare
    p = sub.add_parser("compare", help="Proxy metrics comparison")
    _common_args(p)

    # generate-pool
    p = sub.add_parser("generate-pool", help="Generate TREC annotation pool")
    _common_args(p)
    p.add_argument("--pool-k", type=int, default=20)
    p.add_argument("--out", type=Path, default=None)

    # score-labels
    p = sub.add_parser("score-labels", help="Compute NDCG/MRR from annotated pool")
    _common_args(p)
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--pool-k", type=int, default=20)

    # aggregate
    p = sub.add_parser("aggregate", help="Multi-week significance tests")
    p.add_argument("--author", default=None)

    # subagent-eval
    p = sub.add_parser("subagent-eval", help="Generate Claude qualitative eval prompt")
    _common_args(p)
    p.add_argument("--compare", default=None, help="default: config eval.mechanical.systems")
    p.add_argument("--subagent-k", type=int, default=10)

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help(); return 1

    # Resolve eval defaults from config.yaml (single source of truth).
    cfg = config.load_config()
    mech = cfg.eval_block["mechanical"]
    if hasattr(args, "systems") and args.systems is None:
        args.systems = mech["systems"]
    if hasattr(args, "compare") and args.compare is None:
        args.compare = mech["systems"]
    if hasattr(args, "top_k") and args.top_k is None:
        args.top_k = mech["top_k"] or cfg.prefetch_top_k

    dispatch = {
        "compare": cmd_compare,
        "generate-pool": cmd_generate_pool,
        "score-labels": cmd_score_labels,
        "aggregate": cmd_aggregate,
        "subagent-eval": cmd_subagent_eval,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
