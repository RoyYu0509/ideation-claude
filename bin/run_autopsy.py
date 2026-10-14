#!/usr/bin/env python3
"""bin/run_autopsy.py — READ-ONLY post-mortem of one auto-research run, for the technical report.

Answers ONE question the site exporter does not: *where did a kill signal fire, and what happened to it?*
Every defence in the pipeline (ideation kill-loop, Phase-0 kill-or-confirm, review panel, viability gate,
terminal gate, the human owner) can fire and be overridden. This script reconstructs that chain mechanically
so a run's post-mortem is not a matter of memory.

Zero deps (python3 stdlib only). Never writes into a --run dir.

Reads, all optional (graceful degradation is mandatory — a partial run still yields a row):
  <run>/  milestone-state.json, .terminal-verdict.json, loop-gate-input-r<N>.json, .round-<N>.viability.json,
          .round-<N>.concerns.json, TASK_STATUS.concerns.json, usage-log.json, .scale-contract-review.json,
          HANDOFF.ambition.locked.json, FAILURES.md, .crash-*.json, .forced-*.marker, .reopen-snapshot-r<N>.json,
          EXPERIMENTS/**/ *ledger*.json + result.md, paper/{master,polish-figures-preview}.pdf,
          paper/sections/, paper/review-verdicts.md (+ its git history, for per-round panels)
  <instance>/state/  pipeline-state.json, run-events.jsonl, sessions.jsonl, decisions/DECISIONS-RESOLVED-*.md
  where <instance> is the run dir's grandparent (…/<instance>/runs/<slug>).

Writes: one JSON to --out (default stdout). Schema ar-run-autopsy@1.

SCRUBBING (fail-closed): every emitted string is walked — the run dir's own absolute prefix is stripped, any
remaining /Users/<name> becomes "~". If the literal "/Users/" survives serialization, this exits 2 rather
than write a leaking file.

Usage:
  python3 bin/run_autopsy.py --run ~/test-3/runs/coverage-gap-ltt-context-deployment-gate
  python3 bin/run_autopsy.py --run <dir> --out autopsy.json
  python3 bin/run_autopsy.py --run <a> --run <b> --out corpus.json     # multi-run corpus
"""
import os, sys, re, json, glob, argparse, subprocess
from datetime import datetime, timezone

SCHEMA = "ar-run-autopsy@1"

# ─────────────────────────────────────────────────────────────────────── io
def load_json(path):
    try:
        with open(path, errors="replace") as f:
            return json.load(f)
    except Exception:
        return None

def read_text(path, limit=None):
    try:
        with open(path, errors="replace") as f:
            return f.read(limit) if limit else f.read()
    except Exception:
        return None

def iter_jsonl(path):
    try:
        with open(path, errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except Exception:
        return

def git(repo, *args):
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None

# ───────────────────────────────────────────────────────── scrubbing (fail-closed)
HOME_RE = re.compile(r'/Users/[^/\s"\'\\]+')

def scrub_tree(obj, run_dir=None):
    if isinstance(obj, dict):  return {k: scrub_tree(v, run_dir) for k, v in obj.items()}
    if isinstance(obj, list):  return [scrub_tree(v, run_dir) for v in obj]
    if isinstance(obj, str):
        if run_dir and run_dir in obj:
            obj = obj.replace(run_dir, "")
        return HOME_RE.sub("~", obj)
    return obj

def find_leak(obj, path="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            f = find_leak(v, f"{path}.{k}")
            if f: return f
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            f = find_leak(v, f"{path}[{i}]")
            if f: return f
    elif isinstance(obj, str) and "/Users/" in obj:
        return path
    return None

# ─────────────────────────────────────────────────────────────────── time
def parse_ts(s):
    if not isinstance(s, str) or not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    for cand in (s, s.split(".")[0] + "+00:00"):
        try:
            d = datetime.fromisoformat(cand)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None

def hours_between(a, b):
    ta, tb = parse_ts(a), parse_ts(b)
    if not ta or not tb:
        return None
    return round((tb - ta).total_seconds() / 3600.0, 2)

# ───────────────────────────────────────────────── review panel (robust JSON extraction)
def extract_json_blob(text):
    if not text: return None
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, dict): return obj
    except Exception:
        pass
    for m in re.finditer(r'```(?:json)?\s*\n(.*?)```', text, re.DOTALL):
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict): return obj
        except Exception:
            continue
    i, dec = text.find("{"), json.JSONDecoder()
    while i != -1:
        try:
            obj, _ = dec.raw_decode(text, i)
            if isinstance(obj, dict): return obj
        except Exception:
            pass
        i = text.find("{", i + 1)
    return None

def summarize_panel(text, source):
    """-> {source, round, reviewers, recommendations{}, reject_seats, ac_overall_risk, findings_by_severity{},
           findings_by_attack_class{}} or None."""
    obj = extract_json_blob(text)
    if not isinstance(obj, dict):
        return None
    panel = obj.get("panel")
    if not isinstance(panel, list):
        return None
    recs, sev, attack, reject_seats = {}, {}, {}, []
    for p in panel:
        if not isinstance(p, dict): continue
        rec = p.get("recommendation")
        if rec:
            recs[rec] = recs.get(rec, 0) + 1
            if str(rec).strip().lower() == "reject":
                reject_seats.append(p.get("persona") or p.get("lead_axis") or "?")
        for f in (p.get("findings") or []):
            if not isinstance(f, dict): continue
            s = f.get("severity")
            if s: sev[s] = sev.get(s, 0) + 1
            a = f.get("attack_class")
            if a: attack[str(a)] = attack.get(str(a), 0) + 1
    ac = obj.get("ac") if isinstance(obj.get("ac"), dict) else {}
    return {
        "source": source,
        "round": obj.get("round"),
        "reviewers": len(panel),
        "recommendations": recs,
        "reject_seats": reject_seats,
        "ac_overall_risk": ac.get("overall_risk"),
        "findings_by_severity": sev,
        "findings_by_attack_class": attack,
    }

def load_panels(run_dir):
    """Current review-verdicts.md + every prior version recoverable from paper/'s git history."""
    rel, paper = "review-verdicts.md", os.path.join(run_dir, "paper")
    out, seen = [], set()
    cur = summarize_panel(read_text(os.path.join(paper, rel)), "worktree")
    if cur:
        out.append(cur); seen.add(json.dumps(cur.get("recommendations"), sort_keys=True) + str(cur.get("round")))
    log = git(paper, "log", "--format=%H", "--", rel)
    for sha in (log or "").split():
        blob = git(paper, "show", f"{sha}:{rel}")
        s = summarize_panel(blob, f"git:{sha[:8]}")
        if not s: continue
        key = json.dumps(s.get("recommendations"), sort_keys=True) + str(s.get("round"))
        if key in seen: continue
        seen.add(key); out.append(s)
    out.sort(key=lambda d: (d.get("round") is None, d.get("round") or 0))
    return out

# ────────────────────────────────────────────────────────────── run-dir artifacts
RN_RE = re.compile(r'\.round-(\d+)\.')

def _round_of(path):
    m = RN_RE.search(os.path.basename(path))
    return int(m.group(1)) if m else None

def load_loop_gates(run_dir):
    rows = []
    for p in sorted(glob.glob(os.path.join(run_dir, "loop-gate-input-r*.json"))):
        d = load_json(p)
        if not isinstance(d, dict): continue
        rows.append({
            "round": d.get("round"),
            "overall_risk": d.get("overall_risk"),
            "new_handoff_items": d.get("new_handoff_items"),
            "mismatch": d.get("mismatch"),
        })
    rows.sort(key=lambda r: (r.get("round") is None, r.get("round") or 0))
    return rows

def load_viability(run_dir):
    rows = []
    for p in sorted(glob.glob(os.path.join(run_dir, ".round-*.viability.json"))):
        d = load_json(p)
        if not isinstance(d, dict): continue
        rows.append({
            "round": _round_of(p),
            "block": d.get("block"),
            "recommended_action": d.get("recommended_action"),
            "rescue_tried": os.path.exists(p.replace(".viability.json", ".viability-rescue-tried")),
            "resolved_skip": os.path.exists(p.replace(".viability.json", ".viability-resolved")),
        })
    rows.sort(key=lambda r: (r.get("round") is None, r.get("round") or 0))
    return rows

def _concern_items(d):
    if isinstance(d, list): return d
    if isinstance(d, dict):
        for k in ("open_concerns", "concerns", "items"):
            if isinstance(d.get(k), list): return d[k]
    return []

def load_concerns(run_dir):
    rows = []
    for p in sorted(glob.glob(os.path.join(run_dir, ".round-*.concerns.json"))):
        items = _concern_items(load_json(p))
        sev, st = {}, {}
        for it in items:
            if not isinstance(it, dict): continue
            s = it.get("severity");  sev[s] = sev.get(s, 0) + 1 if s else sev.get(s, 0)
            t = it.get("status");    st[t] = st.get(t, 0) + 1 if t else st.get(t, 0)
        rows.append({"round": _round_of(p), "total": len(items),
                     "by_severity": {k: v for k, v in sev.items() if k},
                     "by_status": {k: v for k, v in st.items() if k}})
    rows.sort(key=lambda r: (r.get("round") is None, r.get("round") or 0))
    final = _concern_items(load_json(os.path.join(run_dir, "TASK_STATUS.concerns.json")))
    fsev, fst = {}, {}
    for it in final:
        if not isinstance(it, dict): continue
        s, t = it.get("severity"), it.get("status")
        if s: fsev[s] = fsev.get(s, 0) + 1
        if t: fst[t] = fst.get(t, 0) + 1
    return rows, {"total": len(final), "by_severity": fsev, "by_status": fst}

def load_experiments(run_dir):
    root = os.path.join(run_dir, "EXPERIMENTS")
    segs = sorted(d for d in glob.glob(os.path.join(root, "*")) if os.path.isdir(d))
    exits, ledger_runs, detached = {}, 0, 0
    for p in glob.glob(os.path.join(root, "**", "*ledger*.json"), recursive=True):
        d = load_json(p)
        runs = d.get("runs") if isinstance(d, dict) else (d if isinstance(d, list) else None)
        for r in (runs or []):
            if not isinstance(r, dict): continue
            ledger_runs += 1
            code = r.get("exit_code")
            exits[str(code)] = exits.get(str(code), 0) + 1
            if r.get("detached"): detached += 1
    crashes = []
    for p in glob.glob(os.path.join(run_dir, ".crash-*.json")):
        d = load_json(p)
        if isinstance(d, dict):
            crashes.append({"exit_code": d.get("exit_code"), "cause_pattern": d.get("cause_pattern") or d.get("cause")})
    return {
        "segments": len(segs),
        "segment_names": [os.path.basename(s) for s in segs],
        "result_files": len(glob.glob(os.path.join(root, "**", "result.md"), recursive=True)),
        "ledger_runs": ledger_runs,
        "exit_codes": exits,
        "detached_runs": detached,
        "crash_records": crashes,
    }

def pdf_pages(path):
    try:
        r = subprocess.run(["pdfinfo", path], capture_output=True, text=True, timeout=20)
        m = re.search(r'^Pages:\s+(\d+)', r.stdout, re.M)
        return int(m.group(1)) if m else None
    except Exception:
        return None

def load_paper(run_dir):
    paper = os.path.join(run_dir, "paper")
    final, kind = None, None
    for name in ("master.pdf", "polish-figures-preview.pdf"):
        p = os.path.join(paper, name)
        if os.path.exists(p):
            final, kind = p, name
            break
    secs = sorted(os.path.basename(s) for s in glob.glob(os.path.join(paper, "sections", "*.tex")))
    return {
        "pdf": kind,
        "compiled_master_pdf": os.path.exists(os.path.join(paper, "master.pdf")),
        "pages": pdf_pages(final) if final else None,
        "sections": secs,
        "has_freeze_report": os.path.exists(os.path.join(paper, "freeze-report.md")),
        "has_edit_report": os.path.exists(os.path.join(paper, "edit-report.md")),
        "has_review_report": os.path.exists(os.path.join(paper, "review-report.md")),
        "diff_ladder_pdfs": len(glob.glob(os.path.join(paper, "diff-ladder", "*.pdf"))),
        "commits": len([l for l in (git(paper, "log", "--format=%H") or "").split() if l]),
    }

# ────────────────────────────────────────────────────────── instance-level state
AUTO_MARKERS = [
    "decide all gates yourself", "fully-automated-gates", "full automation", "full_automation",
    "decision-proxy", "自己判断", "不要停下来问",
]

def load_instance(run_dir):
    inst = os.path.abspath(os.path.join(run_dir, os.pardir, os.pardir))
    state = os.path.join(inst, "state")
    ps = load_json(os.path.join(state, "pipeline-state.json")) or {}
    events = list(iter_jsonl(os.path.join(state, "run-events.jsonl")))
    sessions = list(iter_jsonl(os.path.join(state, "sessions.jsonl")))

    ev_counts, spawn_by_type, spawn_by_model, spawn_by_stage = {}, {}, {}, {}
    for e in events:
        k = e.get("event")
        if k: ev_counts[k] = ev_counts.get(k, 0) + 1
        if k == "agent_spawn":
            for key, bucket in (("subagent_type", spawn_by_type), ("model", spawn_by_model), ("stage", spawn_by_stage)):
                v = e.get(key)
                if v: bucket[str(v)] = bucket.get(str(v), 0) + 1

    decisions, auto_decided = [], 0
    for p in sorted(glob.glob(os.path.join(state, "decisions", "DECISIONS-RESOLVED-*.md"))):
        txt = read_text(p) or ""
        low = txt.lower()
        hits = [m for m in AUTO_MARKERS if m.lower() in low]
        if hits: auto_decided += 1
        decisions.append({"file": os.path.basename(p), "self_decided": bool(hits), "markers": hits[:3]})

    return inst, {
        "pipeline_state": ps,
        "events_total": len(events),
        "events_by_type": ev_counts,
        "spawns_by_subagent_type": spawn_by_type,
        "spawns_by_model": spawn_by_model,
        "spawns_by_stage": spawn_by_stage,
        "sessions": len(sessions),
        "decisions_total": len(decisions),
        "decisions_self_decided": auto_decided,
        "decisions": decisions,
    }

# ─────────────────────────────────────────────────────── the kill-signal chain
# STATUS-MODEL §5: for every non-clean terminal reason the code-computed default is Abandon.
CODE_DEFAULT_ABANDON = {"cap_exit", "negative_result", "over_claim"}

def build_kill_chain(ps, run_dir, panels, gates, viability, terminal, inst_summary):
    ideation_spawns = ((ps.get("stage_budgets_spent") or {}).get("ideation") or {}).get("subagent_spawns")
    integrity = ps.get("ideation_integrity")
    integrity_skipped = isinstance(integrity, str) and "SKIP" in integrity.upper()

    reject_seats = sum(len(p.get("reject_seats") or []) for p in panels)
    ac_verdicts = [p.get("ac_overall_risk") for p in panels if p.get("ac_overall_risk")]

    reason = (terminal or {}).get("reason") or ps.get("terminal_reason")
    code_default = "Abandon" if reason in CODE_DEFAULT_ABANDON else None
    actual = None
    if ps.get("final_status") == "shipped" or ps.get("ship_reason"):
        actual = "Ship"
    elif ps.get("final_status"):
        actual = str(ps["final_status"]).title()

    return {
        "ideation": {
            "subagent_spawns": ideation_spawns,
            "integrity_artifact": integrity,
            "skipped_by_owner": integrity_skipped,
            "ran_for_real": bool(ideation_spawns and ideation_spawns > 5) and not integrity_skipped,
        },
        "phase0": {"verdict": ps.get("phase0_verdict")},
        "review_panel": {
            "panels_recovered": len(panels),
            "reviewer_reject_seats": reject_seats,
            "ac_overall_risk_values": ac_verdicts,
            "ac_reject_count": sum(1 for v in ac_verdicts if str(v).lower() == "reject"),
            "clean_exit_rounds": sum(1 for g in gates if str(g.get("overall_risk")) in ("minor_revision", "accept")),
            "rounds_recorded": len(gates),
        },
        "viability": {
            "rounds": len(viability),
            "blocked_rounds": sum(1 for v in viability if v.get("block")),
            "rescue_tried_rounds": sum(1 for v in viability if v.get("rescue_tried")),
            "actions": [v.get("recommended_action") for v in viability],
        },
        "terminal_gate": {
            "reason": reason,
            "code_default": code_default,
            "actual_disposition": actual,
            "overridden": bool(code_default and actual and code_default != actual),
            "contribution_verdict": (terminal or {}).get("contribution_verdict"),
            "central_claim_alive": (terminal or {}).get("central_claim_alive"),
        },
        "human_acquitter": {
            "full_automation_from": ps.get("full_automation_from"),
            "decisions_total": inst_summary["decisions_total"],
            "decisions_self_decided": inst_summary["decisions_self_decided"],
            "human_in_the_loop": not ps.get("full_automation_from") and inst_summary["decisions_self_decided"] == 0,
        },
    }

def red_flags(kc, gates, paper, scale_review):
    """Every place a kill signal fired and did not stop the run. This is why the script exists."""
    out = []
    idn = kc["ideation"]
    if idn["skipped_by_owner"]:
        out.append("IDEATION SKIPPED — ideation_integrity is SKIPPED_BY_OWNER; the idea kill-loop never ran.")
    elif idn["subagent_spawns"] in (None, 0) or (idn["subagent_spawns"] or 0) <= 5:
        out.append(f"IDEATION NOT EXERCISED — only {idn['subagent_spawns']} ideation spawns; "
                   "the seed bypassed the multi-round kill loop.")
    if str(kc["phase0"]["verdict"]).upper() == "SUSPECT":
        out.append("PHASE-0 SUSPECT — the early kill-or-confirm gate flagged the idea and the run continued.")
    rp = kc["review_panel"]
    if rp["reviewer_reject_seats"] and not rp["ac_reject_count"]:
        out.append(f"REVIEWER REJECT SILENCED — {rp['reviewer_reject_seats']} reviewer seat(s) recommended "
                   f"reject; the AC synthesis returned reject 0 times.")
    if rp["rounds_recorded"] and not rp["clean_exit_rounds"]:
        out.append(f"NO CLEAN ROUND — all {rp['rounds_recorded']} recorded loop-gate rounds were "
                   "major_revision/reject; the loop exited on the round cap, not on merit.")
    tg = kc["terminal_gate"]
    if tg["overridden"]:
        out.append(f"TERMINAL DEFAULT OVERRIDDEN — code default for reason '{tg['reason']}' is "
                   f"{tg['code_default']}; the run recorded {tg['actual_disposition']}.")
    ha = kc["human_acquitter"]
    if ha["full_automation_from"]:
        out.append(f"ACQUITTER REPLACED — full automation armed at {ha['full_automation_from']}; gates after "
                   "that point were resolved by the system, not the owner.")
    elif ha["decisions_self_decided"]:
        out.append(f"ACQUITTER REPLACED — {ha['decisions_self_decided']}/{ha['decisions_total']} archived "
                   "decisions carry a self-decided marker.")
    if any(g.get("mismatch") for g in gates):
        out.append("LOOP-GATE MISMATCH — a round's derived and claimed gate inputs disagreed.")
    if scale_review and str(scale_review.get("verdict", "")).lower() == "incomplete":
        out.append("SCALE-CONTRACT INCOMPLETE — the pre-registered scale contract review did not pass clean.")
    if not paper["compiled_master_pdf"]:
        out.append("NO COMPILED MASTER PDF — the run has no paper/master.pdf; only a preview artifact.")
    return out

# ─────────────────────────────────────────────────────────────────── per run
def autopsy(run_dir):
    run_dir = os.path.abspath(run_dir.rstrip("/"))
    slug = os.path.basename(run_dir)
    inst, isum = load_instance(run_dir)
    ps = isum["pipeline_state"]

    ms = load_json(os.path.join(run_dir, "milestone-state.json")) or {}
    terminal = load_json(os.path.join(run_dir, ".terminal-verdict.json")) or {}
    usage = load_json(os.path.join(run_dir, "usage-log.json")) or {}
    scale_review = load_json(os.path.join(run_dir, ".scale-contract-review.json")) or {}
    ambition = load_json(os.path.join(run_dir, "HANDOFF.ambition.locked.json")) or {}

    gates = load_loop_gates(run_dir)
    viability = load_viability(run_dir)
    concerns_rounds, concerns_final = load_concerns(run_dir)
    panels = load_panels(run_dir)
    experiments = load_experiments(run_dir)
    paper = load_paper(run_dir)

    wall = usage.get("wall") or {}
    first, last = wall.get("first_ts"), wall.get("last_ts")
    totals = usage.get("totals") or {}

    kc = build_kill_chain(ps, run_dir, panels, gates, viability, terminal, isum)

    return {
        "slug": slug,
        "run_dir": run_dir,
        "instance_dir": inst,
        "meta": {
            "run_id": ps.get("run_id") or ms.get("run_id"),
            "venue": ps.get("venue"),
            "seed_file": ps.get("picked_seed_file"),
            "final_status": ps.get("final_status"),
            "exit_reason": ps.get("exit_reason"),
            "last_stage": ps.get("stage"),
            "loop_rounds": ps.get("loop_round"),
            "started_at": first, "finished_at": last,
            "wall_hours": hours_between(first, last),
            "milestones_completed": len([k for k, v in (ms.get("milestones") or {}).items()
                                         if isinstance(v, dict) and v.get("completed_at")]),
            "stages_completed": len([k for k, v in (ms.get("stages") or {}).items()
                                     if isinstance(v, dict) and v.get("completed_at")]),
            "ambition_claim": (ambition.get("central_result") or {}).get("claim"),
            "ambition_evidence_type": (ambition.get("evidence") or {}).get("type"),
        },
        "kill_chain": kc,
        "red_flags": red_flags(kc, gates, paper, scale_review),
        "loop_gates": gates,
        "viability": viability,
        "review_panels": panels,
        "concerns": {"per_round": concerns_rounds, "final": concerns_final},
        "experiments": experiments,
        "paper": paper,
        "scale_contract_review": {"verdict": scale_review.get("verdict")},
        "cost": {
            "out_tokens": totals.get("out_tok"), "in_tokens": totals.get("in_tok"),
            "cache_write": totals.get("cache_write"), "cache_read": totals.get("cache_read"),
            "tool_calls": totals.get("tool_calls"), "agent_transcripts": totals.get("agents"),
            "l0_sessions": isum["sessions"],
            "gates_opened": (usage.get("gates") or {}).get("opened"),
            "gates_answered": (usage.get("gates") or {}).get("answered"),
            "detached": usage.get("detached"),
        },
        "telemetry": {
            "events_total": isum["events_total"],
            "events_by_type": isum["events_by_type"],
            "spawns_by_subagent_type": isum["spawns_by_subagent_type"],
            "spawns_by_model": isum["spawns_by_model"],
            "spawns_by_stage": isum["spawns_by_stage"],
        },
        "decisions": {
            "total": isum["decisions_total"],
            "self_decided": isum["decisions_self_decided"],
            "records": isum["decisions"],
        },
        "backstops": {
            "forced_markers": [os.path.basename(p) for p in sorted(glob.glob(os.path.join(run_dir, ".forced-*.marker")))],
            "reopen_snapshots": len(glob.glob(os.path.join(run_dir, ".reopen-snapshot-r*.json"))),
            "audit_artifact_reviews": len(glob.glob(os.path.join(run_dir, ".round-*.audit-artifact.json"))),
            "failures_md_bytes": os.path.getsize(os.path.join(run_dir, "FAILURES.md"))
                                 if os.path.exists(os.path.join(run_dir, "FAILURES.md")) else None,
        },
    }

# ─────────────────────────────────────────────────────────────────────── main
def main():
    ap = argparse.ArgumentParser(description="Read-only post-mortem of auto-research run(s).")
    ap.add_argument("--run", action="append", required=True, help="run directory (repeatable)")
    ap.add_argument("--out", help="write JSON here (default: stdout)")
    ap.add_argument("--quiet", action="store_true", help="suppress the stderr summary")
    a = ap.parse_args()

    runs = []
    for r in a.run:
        if not os.path.isdir(r):
            print(f"run_autopsy: not a directory: {r}", file=sys.stderr)
            return 2
        runs.append(autopsy(r))

    payload = {"schema": SCHEMA,
               "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "runs": [scrub_tree(r, r["run_dir"]) for r in runs]}

    leak = find_leak(payload)
    if leak:
        print(f"run_autopsy: FAIL — unscrubbed absolute path at {leak}", file=sys.stderr)
        return 2

    text = json.dumps(payload, indent=1, ensure_ascii=False)
    if "/Users/" in text:
        print("run_autopsy: FAIL — '/Users/' survived serialization", file=sys.stderr)
        return 2

    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w") as f:
            f.write(text + "\n")
    else:
        print(text)

    if not a.quiet:
        for r in runs:
            kc, m = r["kill_chain"], r["meta"]
            print(f"\n── {r['slug']}", file=sys.stderr)
            print(f"   rounds={m['loop_rounds']} exit={m['exit_reason']} status={m['final_status']} "
                  f"pages={r['paper']['pages']} wall={m['wall_hours']}h out_tok={r['cost']['out_tokens']}",
                  file=sys.stderr)
            print(f"   panels={kc['review_panel']['panels_recovered']} "
                  f"reviewer_rejects={kc['review_panel']['reviewer_reject_seats']} "
                  f"ac_rejects={kc['review_panel']['ac_reject_count']} "
                  f"clean_rounds={kc['review_panel']['clean_exit_rounds']}/{kc['review_panel']['rounds_recorded']}",
                  file=sys.stderr)
            for f_ in r["red_flags"]:
                print(f"   ⚑ {f_}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
