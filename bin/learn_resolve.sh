#!/usr/bin/env bash
# bin/learn_resolve.sh — DETERMINISTIC run/path resolution for /learn (the post-run retro command).
#
# WHY. /learn must never guess which run it is reviewing, where the source repo lives, or whether the
# pipeline is mid-flight. This script derives all of that from disk ONCE, as parseable KEY lines, so the
# L0 enactment branches on values instead of re-deriving them ad hoc (the loop_gate.sh pattern).
#
# Usage: bin/learn_resolve.sh <data_root> [target]
#   <data_root> = the instance DATA_ROOT (the cwd /auto-research ran in)
#   [target]    = optional: a workspace PATH, a paper slug under runs/, or a run_id prefix.
#                 Absent -> the run in state/pipeline-state.json (fallback: newest runs/<slug> by mtime).
#
# Prints KEY value lines (one per line; consumers parse, never scrape):
#   DATA_ROOT RUN_ID SLUG WS SOURCE_REPO CACHE_ROOT TRACE_DIR SESSIONS_N EVENTS_N
#   DEGRADED (none|events|trace|events+trace)   PIPELINE_BUSY (no|gate:<id>|stage:<stage>)
#   LEARN_DIR LEARN_STATE (new|<path>) DOSSIER_HOME RESOLVED_BY
# exit 0 = resolved; exit 2 = unresolvable (no workspace found / bad target). READ-ONLY — creates nothing.
#
# Env override: AR_LEARN_SOURCE_REPO wins over the marketplace registry (hermetic tests / external boxes).
set -euo pipefail

DATA_ROOT="${1:-}"; TARGET="${2:-}"
[ -n "$DATA_ROOT" ] || { echo "ERROR learn_resolve: need <data_root>"; exit 2; }
[ -d "$DATA_ROOT" ] || { echo "ERROR learn_resolve: data_root not a dir: $DATA_ROOT"; exit 2; }

DATA_ROOT="$DATA_ROOT" TARGET="$TARGET" python3 - <<'PY'
import os, sys, json, glob

root = os.path.realpath(os.environ["DATA_ROOT"]); target = os.environ.get("TARGET", "").strip()

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

ps      = read_json(os.path.join(root, "state", "pipeline-state.json"))
events  = read_jsonl(os.path.join(root, "state", "run-events.jsonl"))
sess    = read_jsonl(os.path.join(root, "state", "sessions.jsonl"))
runsdir = os.path.join(root, "runs")
ws_dirs = [d for d in sorted(glob.glob(os.path.join(runsdir, "*")))
           if os.path.isdir(d) and os.path.basename(d) != "_trace"]
trace_runs = [os.path.basename(d) for d in glob.glob(os.path.join(runsdir, "_trace", "*")) if os.path.isdir(d)]

def die(msg):
    print("ERROR learn_resolve: " + msg); sys.exit(2)

# ---- resolve slug/ws (target wins; else pipeline-state; else newest runs/<slug>) ----
slug = ws = None; resolved_by = None; run_id = None
if target:
    tpath = os.path.realpath(target) if os.path.isdir(target) else None
    if tpath and os.path.isfile(os.path.join(tpath, "milestone-state.json")):
        ws, slug, resolved_by = tpath, os.path.basename(tpath), "arg-path"
    elif os.path.isdir(os.path.join(runsdir, target)):
        slug, resolved_by = target, "arg-slug"
    else:
        cands = sorted({e.get("run_id") for e in events if e.get("run_id")} | set(trace_runs))
        hits = [r for r in cands if r and r.startswith(target)]
        if len(hits) == 1:
            run_id, resolved_by = hits[0], "arg-runid"
            papers = [e.get("paper") for e in events if e.get("run_id") == run_id and e.get("paper")]
            slug = papers[-1] if papers else ps.get("paper_slug")
        elif len(hits) > 1:
            die("run_id prefix '%s' is ambiguous: %s" % (target, ", ".join(hits)))
        else:
            die("target '%s' matches no workspace path, no runs/<slug>, no run_id" % target)
if slug is None:
    slug = ps.get("paper_slug")
    resolved_by = resolved_by or ("state" if slug else None)
if slug is None:
    if not ws_dirs: die("no workspace found (no pipeline-state.paper_slug, no runs/<slug> dirs)")
    ws = max(ws_dirs, key=os.path.getmtime); slug = os.path.basename(ws); resolved_by = "fallback-mtime"
if ws is None:
    ws = os.path.join(runsdir, slug)
if not os.path.isdir(ws): die("workspace dir missing: %s" % ws)

# ---- run_id (state -> events-for-this-paper -> single _trace dir -> synthetic) ----
if run_id is None:
    run_id = ps.get("run_id")
if run_id is None:
    ids = [e.get("run_id") for e in events if e.get("run_id") and e.get("paper") in (slug, None)]
    run_id = ids[-1] if ids else None
if run_id is None and len(trace_runs) == 1:
    run_id = trace_runs[0]
if run_id is None:
    run_id = "untraced-" + slug

trace_dir = os.path.join(runsdir, "_trace", run_id)
has_trace = os.path.isdir(trace_dir)

# ---- degraded + busy ----
deg = []
if not events: deg.append("events")
if not has_trace and not sess: deg.append("trace")
degraded = "+".join(deg) if deg else "none"
busy = "no"
if ps.get("pending_gate"):
    busy = "gate:%s" % ps["pending_gate"]
elif ps.get("stage") not in (None, "", "done") and ps.get("paper_slug") == slug:
    busy = "stage:%s" % ps["stage"]

# ---- source repo + cache root ----
src = os.environ.get("AR_LEARN_SOURCE_REPO", "")
if not src:
    try:
        mk = json.load(open(os.path.expanduser("~/.claude/plugins/known_marketplaces.json")))
        src = mk["auto-research"]["source"]["path"]
    except Exception:
        src = ""
if src and not os.path.isdir(src): src = ""
cache = os.path.expanduser("~/.claude/plugins/cache/auto-research")
if not os.path.isdir(cache): cache = ""

learn_dir = os.path.join(root, "state", "learning", run_id)
learn_state = os.path.join(learn_dir, "learn-state.json")
dossier_home = os.path.join(src, "dev", "learning") if src else os.path.join(learn_dir, "repo-outbox")

for k, v in [("DATA_ROOT", root), ("RUN_ID", run_id), ("SLUG", slug), ("WS", ws),
             ("SOURCE_REPO", src or "none"), ("CACHE_ROOT", cache or "none"),
             ("TRACE_DIR", trace_dir if has_trace else "none"),
             ("SESSIONS_N", len(sess)), ("EVENTS_N", len(events)),
             ("DEGRADED", degraded), ("PIPELINE_BUSY", busy),
             ("LEARN_DIR", learn_dir),
             ("LEARN_STATE", learn_state if os.path.isfile(learn_state) else "new"),
             ("DOSSIER_HOME", dossier_home), ("RESOLVED_BY", resolved_by)]:
    print("%s %s" % (k, v))
PY
