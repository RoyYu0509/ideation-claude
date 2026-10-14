#!/usr/bin/env python3
"""bin/learn_manifest.py — P0 of /learn: the MECHANICAL run manifest (zero LLM).

Maps every artifact a run left on disk back to the pipeline component group that produced it, slices the
semantic event stream per group (so no reviewer greps the whole thing), and snapshots WHICH CODE ACTUALLY
RAN (per-plugin cache-vs-source spot shas + the run's frozen spec_commit) — the validity precondition for
every downstream judgment. Tolerates artifact-name drift across run vintages (GLOB FAMILIES, old + new
names) and degrades honestly for pre-trace runs (no events/sessions -> flags, never guesses).

Writes into --out-dir (default <data_root>/state/learning/<run_id>/):
  manifest.json          the full machine record (schema auto-research-learn-manifest@1)
  manifest-summary.md    <=60 lines — the ONLY manifest artifact the /learn L0 reads
  events-<G>.jsonl       per-group event slices (A B C D E meta), run_id-filtered

PURE WRITER of its own out-dir; never touches run artifacts. stdlib only.
Usage: learn_manifest.py --data-root D [--ws W --run-id R --slug S --source-repo P --cache-root C]
                         [--out-dir O]
(learn.js passes the values from bin/learn_resolve.sh; absent ones are minimally re-derived.)
"""
import os, sys, re, json, glob, hashlib, argparse, subprocess, datetime

SCHEMA = "auto-research-learn-manifest@1"

# ---------------------------------------------------------------- artifact registry
# (family_id, group, component, scope ws|root, expect always|completed|conditional, [patterns old+new])
REGISTRY = [
    # A — ideation (DATA_ROOT scope; a data/ dir spans weeks, counts are informational)
    ("a-profile",        "A", "profile builder",        "root", "conditional", ["data/profile/*"]),
    ("a-candidate-pool", "A", "prefetch/rerank pool",   "root", "conditional",
     ["data/cache/week-*-scout.json", "data/cache/week-*-rerank.json", "data/cache/gated-pool*.json",
      "data/cache/week-*-gated-pool.json",   # P-6 fix (dossier 02, 2026-07-07): real filename is week-<W>-gated-pool.json
      "data/cache/week-*-candidates.json", "data/cache/week-*-prefetched.json",
      "data/cache/week-*-judge-cache.json", "data/cache/week-*-quality-gate.json"]),   # quality-ceiling
      # upgrade (2026-07-07): the full pool + prefetch scores + judge near-miss verdicts are the D4
      # ideation-ceiling evidence — they were never indexed before (add-never-replace).
    ("a-pool-snapshot",  "A", "ideation pool snapshot (at pick)", "ws", "conditional",
     ["ideation-pool-snapshot/snapshot-manifest.json", "ideation-pool-snapshot/*/*",
      "ideation-pool-snapshot/*/*/*"]),   # durable copy taken by bin/snapshot_ideation_pool.py at
      # seed-pick time — survives the scout's ~7-day cache cleanup; X-quality §3 reads this first.
    ("a-ideations",      "A", "ideate/refine outputs",  "root", "conditional",
     ["data/ideations/*/*.json", "data/ideations/*/refined/*.md", "data/refined/*/*"]),
    ("a-integrity",      "A", "ideation-integrity auditor", "root", "conditional", ["data/ideations/*/.integrity.json"]),
    ("a-web-digest",     "A", "weekly digest",          "root", "conditional", ["data/web/*-scout.html"]),
    # B — seed -> HANDOFF
    ("b-handoff",        "B", "seed_to_handoff author", "ws", "always",      ["HANDOFF.md"]),
    ("b-handoff-exports","B", "per-round demand exports","ws", "conditional", ["HANDOFF-*.md"]),
    ("b-scale-lock",     "B", "SCALE-CONTRACT lock",    "ws", "completed",   ["HANDOFF.scale-contract.locked.json"]),
    ("b-ambition-lock",  "B", "AMBITION-CONTRACT lock", "ws", "completed",   ["HANDOFF.ambition.locked.json"]),
    ("b-ambition-target","B", "amplifier raised target","ws", "conditional", ["HANDOFF.ambition.target.json"]),
    ("b-protocol-copy",  "B", "protocol copy",          "ws", "always",      ["RESEARCH-PROTOCOL.md"]),
    ("b-scale-review",   "B", "M1 scale reviewer",      "ws", "conditional", [".scale-contract-review.json"]),
    # C1 — experiment chain
    ("c1-experiments",   "C1", "experiment segments",   "ws", "completed",
     ["EXPERIMENTS/*/result.md", "EXPERIMENTS/*/metrics*.json", "EXPERIMENTS/PHASE*/*"]),
    ("c1-wave-ledgers",  "C1", "exp provenance ledgers","ws", "completed",
     ["EXPERIMENTS/wave*.ledger.json", "EXPERIMENTS/*/wave*.ledger.json", ".polish/*.ledger.json",
      "EXPERIMENTS/wave-ledger.json", "EXPERIMENTS/*/wave-ledger.json"]),   # P-6 fix (dossier 02, 2026-07-07):
      # real filename is hyphenated "wave-ledger.json" (one per wave dir), which "wave*.ledger.json" does NOT
      # match (the "*" would have to consume "-ledger" then still find a literal ".ledger.json" suffix — it
      # doesn't); old patterns kept for older-vintage runs (GLOB FAMILIES tolerate drift, never replace).
    ("c1-detach-logs",   "C1", "detached stdout logs",  "ws", "conditional",
     [".polish/logs/*.stdout.log", "EXPERIMENTS/*/logs/*"]),   # P-6 fix: real logs live under
      # EXPERIMENTS/<wave>/logs/* (stdout.log + exitcode), not .polish/logs/ — this run's manifest undercounted
      # 6 wave-ledgers + 12 log files to zero because of exactly these two stale patterns.
    ("c1-results-rollup","C1", "results roll-ups",      "ws", "conditional",
     ["EXPERIMENTS/results_master.json", "EXPERIMENTS/RESULTS-SUMMARY.md"]),
    ("c1-audit-gate",    "C1", "audit-artifact gate",   "ws", "completed",
     ["AUDIT-ARTIFACTS.locked.json", ".round-*.audit-artifact*.json", ".audit-artifact-review.json"]),
    ("c1-audited-values","C1", "audited-values registry","ws","completed",   ["AUDITED-VALUES.json"]),
    ("c1-science-scratch","C1","worker science scratch","ws", "conditional",
     ["THEORY.md", "CLAIMS.md", "TASK_STATUS.md", "TASK_STATUS.concerns.json"]),
    ("c1-living-logs",   "C1", "living logs",           "ws", "always",
     ["RESEARCH_LOG.md", "DECISIONS.md", "FAILURES.md"]),
    ("c1-literature",    "C1", "literature milestone",  "ws", "completed",
     ["differentiation_table.md", "paper/references.bib", "EXPERIMENTS/lit/*", ".literature-review.json"]),
    # C2 — review / verify / gate chain (+ drafter)
    ("c2-review-history","C2", "review round history",  "ws", "completed",
     ["REVIEW/round*_reviews.md", "REVIEW_ROUND_*.md"]),
    ("c2-review-last",   "C2", "review AC synthesis",   "ws", "completed",
     ["paper/review-report.md", "paper/review-verdicts.md", "paper/paper-model.md"]),
    ("c2-verify",        "C2", "verifier reports",      "ws", "completed",
     ["VERIFICATION-REPORT.md", "VERIFY_FINAL_REPORT.md"]),
    ("c2-verify-belt",   "C2", "mechanical verify belt","ws", "conditional", [".verify-preflight.json"]),
    ("c2-gate-inputs",   "C2", "loop-gate inputs",      "ws", "completed",
     ["loop-gate-input-r*.json", "loop_gate_input_r*.json"]),
    ("c2-round-markers", "C2", "round markers",         "ws", "completed",
     [".round-*.start", ".round-*.concerns.json", ".round-*.drafted"]),
    ("c2-viability",     "C2", "viability/rescue sidecars","ws","conditional",
     [".round-*.viability*", ".round-*.*-tried", ".forced-*.marker", ".reopen-snapshot-*.json",
      ".round-*.rescue-verdicts.json"]),   # quality-ceiling upgrade: rescue residuals persisted per round
    ("c2-amplify",       "C2", "ambition amplifier verdicts","ws","conditional",
     [".round-*.amplify-verdict.json"]),   # quality-ceiling upgrade (2026-07-07): BOTH outcomes persist
      # (raised + at_ceiling with rationale/earnable) — the at-ceiling call used to leave only an event
      # line; this is the [OPPORTUNITY] lane's headroom-signal evidence. c2-viability's ".round-*.*-tried"
      # does NOT match this name (needs the -tried suffix), hence a dedicated family.
    ("c2-terminal",      "C2", "terminal gate verdicts","ws", "conditional",
     [".terminal-verdict.json", ".terminal-narrowing-accepted.md"]),
    # C2 review-chain science record: the loop reviews the DOSSIER, not a manuscript (writing-redesign 2026-07-07)
    ("c2-dossier",       "C2", "findings dossier (review record)", "ws", "completed", ["FINDINGS-DOSSIER.md"]),
    ("c2-reframe",       "C2", "reframe pass",          "ws", "conditional", ["FRAMING-REVISION.md"]),
    # D — SPEC DELIVERY (spec re-aim 2026-08-30) + ship. The loop's product is the SPECIFICATION: every
    # (re-)author is versioned into SPEC/, and spec_freeze distils the settled one into SPEC-FINAL.md.
    ("d-spec-versions",  "D", "per-round spec versions", "ws", "always",     ["SPEC/SPEC-v*.md"]),
    ("d-spec-ledger",    "D", "spec evolution ledger",   "ws", "always",     ["SPEC/spec-ledger.json"]),
    ("d-spec-final",     "D", "the delivered spec",      "ws", "completed",  ["SPEC-FINAL.md"]),
    ("d-spec-evolution", "D", "spec evolution write-up", "ws", "completed",  ["SPEC-EVOLUTION.md"]),
    ("d-spec-freeze",    "D", "spec freeze audit",       "ws", "completed",  ["SPEC-FREEZE-REPORT.md"]),
    # legacy (pre-2026-08-30 runs): the retired writing engine's manuscript chain — glob-tolerant, absent now
    ("d-legacy-finish",  "D", "legacy manuscript chain", "ws", "conditional",
     ["FINDINGS.json", "paper/OUTLINE.json", "paper/sections/*", "paper/master.tex",
      "paper/figure-design-briefs.*", "paper/polish-figures-report.md", "paper/edit-report.md",
      "paper/freeze-report.md", "paper/rewrite-report.md", "paper/rewrite-diff.*",
      "paper/cross-check-report.md", "paper/flowchart-report.md", "paper/diff-ladder/*"]),
    ("d-final-report",   "D", "run report",             "ws", "completed",   ["FINAL-REPORT.md", "FINAL-REPORT-killed.md"]),
    ("d-milestone-ledger","D","milestone-state ledger", "ws", "always",      ["milestone-state.json"]),
    ("d-frozen-config",  "D", "frozen config snapshot", "ws", "always",      [".config-frozen.yaml"]),
    # F — L0 meta / observability
    ("f-pipeline-state", "F", "pipeline state",         "root", "always",    ["state/pipeline-state.json"]),
    ("f-events",         "F", "run-events stream",      "root", "completed", ["state/run-events.jsonl"]),
    ("f-sessions",       "F", "session ledger",         "root", "completed", ["state/sessions.jsonl"]),
    ("f-decisions",      "F", "resolved human gates",   "root", "completed", ["state/decisions/DECISIONS-RESOLVED-*.md"]),
    ("f-decisions-open", "F", "pending gate",           "root", "conditional", ["state/decisions/DECISIONS-PENDING.md"]),
]

STAGE_TO_GROUP = {
    "ideation": "A",
    "seed_gate": "B", "gen_handoff": "B", "handoff_gate": "B", "seed_to_handoff": "B",
    "loop": "C",
    # terminal chain (spec re-aim 2026-08-30): verify_final -> spec_freeze -> ship
    "verify_final": "D", "spec_freeze": "D", "ship": "D", "terminal": "D",
    # legacy aliases (the retired writing engine + its predecessors)
    "freeze_findings": "D", "story": "D", "write": "D", "figures": "D", "edit": "D", "freeze": "D",
    "rewrite": "D", "polish_figures": "D", "cross_check": "D", "finishing": "D",
    # Group E (公众号 publishing) was RETIRED 2026-08-30 with the wechat-publish-ar plugin (inactive/);
    # its artifact family and its (always-empty) event-slice mapping are both gone.
}

def sha256(path, cap=4 * 1024 * 1024):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(65536)
                if not b: break
                h.update(b)
        return h.hexdigest()[:16]
    except Exception:
        return None

def read_json(p):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}

def read_jsonl(p):
    out = []
    try:
        with open(p, errors="replace") as f:
            for l in f:
                l = l.strip()
                if not l: continue
                try: out.append(json.loads(l))
                except Exception: pass
    except Exception: pass
    return out

def collect_family(base, patterns):
    hits, matched_pats = [], []
    for pat in patterns:
        got = sorted(glob.glob(os.path.join(base, pat)))
        got = [g for g in got if os.path.exists(g)]
        if got: matched_pats.append(pat)
        hits += got
    seen, uniq = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h); uniq.append(h)
    return uniq, matched_pats

# ---------------------------------------------------------------- scaffold-vs-drafted (P-6 fix, dossier 02,
# 2026-07-07): "d-sections" (paper/sections/*) and "d-master-tex" (paper/master.tex) are found by bare
# glob.glob/os.path.exists alone, which cannot tell an UNTOUCHED venue-skeleton scaffold file from real
# drafted content — a C2/D reviewer had to hand-diff against assets/paper-skeleton*/ and read git log to
# learn this run's paper/sections/*.tex were 100% untouched scaffold. Generalize that manual check: a hit is
# "scaffold" iff its content is byte-identical to the SAME relpath in ANY assets/paper-skeleton*/ variant.
SCAFFOLD_CHECK_FAMILIES = {"d-sections", "d-master-tex"}

def skeleton_shas(assets_root):
    """relpath (from a paper-skeleton*/ variant root, e.g. 'sections/methods.tex', 'master.tex') -> the set of
    sha256(16-hex) values seen for that relpath across every variant. Tolerates a missing/unresolvable assets
    root (degrade honestly — the caller just gets no scaffold signal, never a guess)."""
    table = {}
    if not assets_root or not os.path.isdir(assets_root): return table
    for variant in sorted(glob.glob(os.path.join(assets_root, "paper-skeleton*"))):
        if not os.path.isdir(variant): continue
        for f in glob.glob(os.path.join(variant, "**", "*"), recursive=True):
            if not os.path.isfile(f): continue
            h = sha256(f)
            if not h: continue
            table.setdefault(os.path.relpath(f, variant), set()).add(h)
    return table

# ---------------------------------------------------------------- code worlds
PLUGIN_SPOTS = {
    # hooks/ included since the first /learn dry-run's own verify pass (LMV-1): spawn_guard/ship_gate drift
    # between cache and source is exactly the class this snapshot exists to surface.
    "auto-research":       ["spec/research.js", "spec/learn.js", "bin/loop_gate.sh", "bin/verify_panel.sh",
                            "spec/spawn-prompts/VERIFY-PROTOCOL.md", "hooks/spawn_guard.py",
                            "hooks/ship_gate.py", "hooks/decision_guard.py"],
    "paper-polish-ar":     ["spec/review-protocol.md", "spec/polish-figures.js"],
    "experiment-lab-ar":   ["spec/experiment-protocol.md"],
    "arxiv-recommender-ar":["workflows/arxiv-scout.js"],
}

def source_path(src, plugin, rel):
    # the root plugin lives at the repo root; sub-plugins under plugins/<name>/
    return os.path.join(src, rel) if plugin == "auto-research" else os.path.join(src, "plugins", plugin, rel)

def code_worlds(src, cache_root, ws):
    worlds = {"source_repo": src or None, "cache_root": cache_root or None,
              "source_head": None, "run_spec_commit": None, "plugins": {}}
    if src:
        try:
            r = subprocess.run(["git", "-C", src, "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0: worlds["source_head"] = r.stdout.strip()
        except Exception: pass
    frozen = (read_json(os.path.join(ws, "milestone-state.json")) or {}).get("frozen") or {}
    worlds["run_spec_commit"] = frozen.get("spec_commit")
    for plug, spots in PLUGIN_SPOTS.items():
        cdirs = sorted(glob.glob(os.path.join(cache_root, plug, "*"))) if cache_root else []
        cdir = cdirs[-1] if cdirs else None
        materialized = bool(cdir) and any(os.path.isdir(os.path.join(cdir, d)) for d in ("spec", "workflows", "bin", "skills"))
        entry = {"loaded_from": "cache" if materialized else "source",
                 "cache_dir": cdir if materialized else None, "spots": {}, "drift": False}
        for rel in spots:
            sp = source_path(src, plug, rel) if src else None
            cp = os.path.join(cdir, rel) if materialized else None
            s_sha = sha256(sp) if sp and os.path.isfile(sp) else None
            c_sha = sha256(cp) if cp and os.path.isfile(cp) else None
            spot = {"source_sha": s_sha, "cache_sha": c_sha}
            if s_sha and c_sha and s_sha != c_sha:
                spot["drift"] = True; entry["drift"] = True
            entry["spots"][rel] = spot
        worlds["plugins"][plug] = entry
    return worlds

# ---------------------------------------------------------------- main build
def build(args):
    root = os.path.realpath(args.data_root)
    ps = read_json(os.path.join(root, "state", "pipeline-state.json"))
    slug = args.slug or ps.get("paper_slug")
    ws = args.ws
    if not ws:
        if slug and os.path.isdir(os.path.join(root, "runs", slug)):
            ws = os.path.join(root, "runs", slug)
        else:
            cands = [d for d in glob.glob(os.path.join(root, "runs", "*"))
                     if os.path.isdir(d) and os.path.basename(d) != "_trace"]
            if not cands:
                print("ERROR learn_manifest: no workspace found under %s/runs" % root); sys.exit(2)
            ws = max(cands, key=os.path.getmtime); slug = os.path.basename(ws)
    ws = os.path.realpath(ws); slug = slug or os.path.basename(ws)
    events = read_jsonl(os.path.join(root, "state", "run-events.jsonl"))
    run_id = args.run_id or ps.get("run_id") or \
        next((e.get("run_id") for e in reversed(events) if e.get("run_id")), None) or ("untraced-" + slug)
    out_dir = args.out_dir or os.path.join(root, "state", "learning", run_id)
    os.makedirs(out_dir, exist_ok=True)

    completed = (ps.get("stage") == "done") or \
        os.path.isfile(os.path.join(ws, "FINAL-REPORT.md")) or os.path.isfile(os.path.join(ws, "FINAL-REPORT-killed.md"))

    skel = skeleton_shas(os.path.join(args.source_repo, "assets")) if args.source_repo else {}

    groups, gaps, total = {}, [], 0
    for fam, grp, comp, scope, expect, pats in REGISTRY:
        base = ws if scope == "ws" else root
        hits, matched = collect_family(base, pats)
        total += len(hits)
        rec = {"family": fam, "component": comp, "count": len(hits),
               "matched_patterns": matched,
               "paths": [os.path.relpath(h, base) for h in hits[:40]],
               "scope": scope, "expect": expect}
        if len(hits) > 40: rec["paths_truncated"] = len(hits) - 40
        if fam in SCAFFOLD_CHECK_FAMILIES and skel:
            scaffold, drafted = [], []
            for h in hits:
                rel = os.path.relpath(h, os.path.join(ws, "paper"))
                hsha = sha256(h)
                (scaffold if (hsha and hsha in skel.get(rel, ())) else drafted).append(os.path.relpath(h, base))
            rec["scaffold_vs_drafted"] = {"scaffold": scaffold, "drafted": drafted,
                "note": "byte-identical to the same relpath in a known assets/paper-skeleton*/ variant = untouched scaffold, never drafted"}
        groups.setdefault(grp, {"artifacts": [], "event_slice": None, "event_count": 0})["artifacts"].append(rec)
        if not hits and (expect == "always" or (expect == "completed" and completed)):
            gaps.append({"family": fam, "group": grp, "component": comp, "expect": expect,
                         "note": "expected by the current spec but absent on disk"})

    # ---- event slices (single-assignment by stage; unmatched -> meta) ----
    run_events = [e for e in events if e.get("run_id") in (run_id, None)]
    slices = {g: [] for g in ("A", "B", "C", "D", "E", "meta")}
    for e in run_events:
        slices[STAGE_TO_GROUP.get(e.get("stage"), "meta")].append(e)
    for g, evs in slices.items():
        p = os.path.join(out_dir, "events-%s.jsonl" % g)
        with open(p, "w") as f:
            for e in evs: f.write(json.dumps(e, ensure_ascii=False) + "\n")
        tgt = {"A": "A", "B": "B", "C": "C1", "D": "D", "E": "E", "meta": "F"}[g]
        groups.setdefault(tgt, {"artifacts": [], "event_slice": None, "event_count": 0})
        groups[tgt]["event_slice"] = p; groups[tgt]["event_count"] = len(evs)
    if "C1" in groups:  # C1 and C2 share the loop slice
        groups.setdefault("C2", {"artifacts": [], "event_slice": None, "event_count": 0})
        groups["C2"]["event_slice"] = groups["C1"]["event_slice"]
        groups["C2"]["event_count"] = groups["C1"]["event_count"]

    # ---- trace stats + code worlds ----
    sessions = read_jsonl(os.path.join(root, "state", "sessions.jsonl"))
    trace_dir = os.path.join(root, "runs", "_trace", run_id)
    agent_files = glob.glob(os.path.join(trace_dir, "*", "subagents", "agent-*.jsonl")) if os.path.isdir(trace_dir) else []
    degraded = {"events": not events, "sessions": not sessions, "trace": not os.path.isdir(trace_dir)}
    worlds = code_worlds(args.source_repo or "", args.cache_root or "", ws)

    manifest = {
        "schema": SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id, "slug": slug, "data_root": root, "workspace": ws,
        "pipeline": {k: ps.get(k) for k in ("stage", "loop_round", "final_status", "exit_reason",
                                            "venue", "pending_gate", "verify_verdict") if k in ps},
        "picked_seed_file": ps.get("picked_seed_file"),
        "completed": completed, "degraded": degraded,
        "code_worlds": worlds,
        "trace": {"sessions": len(sessions), "trace_dir": trace_dir if os.path.isdir(trace_dir) else None,
                  "agent_transcripts": len(agent_files), "events_total": len(run_events)},
        "groups": groups, "gaps": gaps, "artifact_total": total,
    }
    mpath = os.path.join(out_dir, "manifest.json")
    with open(mpath, "w") as f: json.dump(manifest, f, ensure_ascii=False, indent=1)

    # ---- summary (hard cap 60 lines) ----
    drifted = [p for p, e in worlds["plugins"].items() if e["drift"]]
    L = []
    L.append("# RUN MANIFEST — %s (%s)" % (slug, run_id))
    L.append("- data_root: %s" % root)
    L.append("- pipeline: stage=%s rounds=%s final=%s exit=%s venue=%s" % (
        ps.get("stage"), ps.get("loop_round"), ps.get("final_status"), ps.get("exit_reason"), ps.get("venue")))
    L.append("- completed=%s · degraded: events=%s sessions=%s trace=%s" % (
        completed, degraded["events"], degraded["sessions"], degraded["trace"]))
    L.append("- trace: %d session(s), %d agent transcript(s), %d event(s)" % (
        len(sessions), len(agent_files), len(run_events)))
    L.append("- code: run_spec_commit=%s · source_head=%s · DRIFTED plugins: %s" % (
        worlds["run_spec_commit"], worlds["source_head"], ", ".join(drifted) if drifted else "none"))
    for plug, e in worlds["plugins"].items():
        L.append("  - %s: loaded_from=%s%s" % (plug, e["loaded_from"], " ⚠️ cache≠source" if e["drift"] else ""))
    L.append("## groups (artifact families found / listed)")
    for g in ("A", "B", "C1", "C2", "D", "E", "F"):
        if g not in groups: continue
        arts = groups[g]["artifacts"]
        found = sum(1 for a in arts if a["count"]); n = sum(a["count"] for a in arts)
        L.append("- %s: %d/%d families present, %d file(s), %d event(s) -> %s" % (
            g, found, len(arts), n, groups[g].get("event_count") or 0,
            os.path.basename(groups[g]["event_slice"] or "-")))
    L.append("## gaps (expected but absent — evidence, not yet findings)")
    if gaps:
        for gp in gaps[:10]:
            L.append("- [%s] %s (%s): %s" % (gp["group"], gp["family"], gp["component"], gp["note"]))
        if len(gaps) > 10: L.append("- … +%d more (see manifest.json)" % (len(gaps) - 10))
    else:
        L.append("- none")
    L = L[:60]
    spath = os.path.join(out_dir, "manifest-summary.md")
    with open(spath, "w") as f: f.write("\n".join(L) + "\n")

    print("OK learn_manifest: run=%s groups=%d artifacts=%d gaps=%d drifted=%s degraded=%s" % (
        run_id, len(groups), total, len(gaps), ",".join(drifted) or "none",
        "+".join(k for k, v in degraded.items() if v) or "none"))
    print("MANIFEST %s" % mpath)
    print("SUMMARY %s" % spath)

def main():
    ap = argparse.ArgumentParser(prog="learn_manifest.py")
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--ws"); ap.add_argument("--run-id"); ap.add_argument("--slug")
    ap.add_argument("--source-repo", default=os.environ.get("AR_LEARN_SOURCE_REPO", ""))
    ap.add_argument("--cache-root", default=os.path.expanduser("~/.claude/plugins/cache/auto-research"))
    ap.add_argument("--out-dir")
    args = ap.parse_args()
    if args.cache_root and not os.path.isdir(args.cache_root): args.cache_root = ""
    if args.source_repo and not os.path.isdir(args.source_repo): args.source_repo = ""
    build(args)

if __name__ == "__main__":
    main()
