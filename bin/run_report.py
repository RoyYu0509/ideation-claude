#!/usr/bin/env python3
"""bin/run_report.py — READ-ONLY attribution reader for an auto-research run.

The cure for "L1/L2 went dark": it stitches our semantic event stream (state/run-events.jsonl) to Claude
Code's native per-agent transcripts (the snapshot under runs/_trace/<run_id>/ if present, else the live
~/.claude/projects/<slug>/<session>/ dir). The join key is agent_id (= subagents/agent-<id>.jsonl filename
= jsonl `agentId`). Parent edges come from each subagent's meta.json `toolUseId` (the tool_use id of the
Agent call that spawned it), which lets us rebuild the WHOLE L0->L1->L2 tree, the one native /agents can't
drill into.

PURE READER — never writes, never mutates state. Zero deps (python3 stdlib only).

Subcommands:
  timeline  [--paper P] [--run R]               semantic event sequence, real UTC
  tree      [--run R] [--session SID]           rebuilt L0->L1->L2 agent tree + per-node stats + semantic tags
  agent ID  [--run R] [--session SID]           full per-tool action trace of ONE agent (prefix match ok)
  attribute PATTERN [--run R] [--session SID]   which agent/transcript emitted a string/number (regex)
  health    [--paper P] [--run R]               auto red/green flags (RC-1/2/3/4/6/9/13 + seam)
  rollup    [--run R] [--session SID] [--out F] machine-readable per-run totals JSON (tokens by role/model,
                                                spawns by stage, gate open->answer spans, detach stats) —
                                                the /learn economics input; derives, never persists

--session targets a single native session directly (great for forensics on a past run); otherwise the run's
sessions come from state/sessions.jsonl (filtered by run_id), falling back to the newest project jsonl.
"""
import os, sys, re, json, glob, argparse, subprocess

def repo_root():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROOT = repo_root()

# ---------------------------------------------------------------- locating
def project_slug(root):    return re.sub(r"[^A-Za-z0-9]", "-", root)
def native_proj_dir(root): return os.path.expanduser(os.path.join("~/.claude/projects", project_slug(root)))

def read_jsonl(path):
    out = []
    if path and os.path.exists(path):
        with open(path, errors="replace") as f:
            for l in f:
                l = l.strip()
                if not l: continue
                try:    out.append(json.loads(l))
                except Exception: pass
    return out

def load_events(root):   return read_jsonl(os.path.join(root, "state", "run-events.jsonl"))
def load_sessions(root): return read_jsonl(os.path.join(root, "state", "sessions.jsonl"))

def current_run_id(root, events=None):
    try:
        rid = json.load(open(os.path.join(root, "state", "pipeline-state.json"))).get("run_id")
        if rid: return rid
    except Exception: pass
    for e in reversed(events if events is not None else load_events(root)):
        if e.get("run_id"): return e["run_id"]
    return None

def resolve_sessions(root, run_id, session_override=None):
    if session_override:
        tp = os.path.join(native_proj_dir(root), session_override + ".jsonl")
        return [{"session_id": session_override, "transcript_path": tp}]
    sess = load_sessions(root)
    if run_id:
        sess = [s for s in sess if s.get("run_id") in (run_id, None)] or sess
    if sess:
        return [{"session_id": s.get("session_id"), "transcript_path": s.get("transcript_path") or ""}
                for s in sess if s.get("session_id")]
    cands = glob.glob(os.path.join(native_proj_dir(root), "*.jsonl"))   # fallback: newest project jsonl
    if not cands: return []
    newest = max(cands, key=os.path.getmtime)
    return [{"session_id": os.path.basename(newest)[:-6], "transcript_path": newest}]

def session_paths(root, run_id, s):
    """(main_transcript_path, subagents_dir) — snapshot under runs/_trace/<run_id>/ wins over live native."""
    sid, tp = s["session_id"], s.get("transcript_path") or ""
    if run_id:
        snap = os.path.join(root, "runs", "_trace", run_id, sid)
        if os.path.isdir(snap):
            main = os.path.join(snap, os.path.basename(tp) if tp else sid + ".jsonl")
            return (main if os.path.exists(main) else "", os.path.join(snap, "subagents"))
    sessdir = tp[:-6] if tp.endswith(".jsonl") else os.path.join(native_proj_dir(root), sid)
    return (tp, os.path.join(sessdir, "subagents"))

# ---------------------------------------------------------------- model
def jsonl_stats(path):
    rec = tools = out_tok = in_tok = cache_w_tok = cache_r_tok = 0
    first = last = model = None
    seen_msg_ids = set()   # one API response often splits into several JSONL lines (one per content
                            # block: thinking/text/tool_use), each repeating the SAME message.usage —
                            # count each message.id once or usage is overcounted per extra block.
    for d in read_jsonl(path):
        rec += 1
        ts = d.get("timestamp")
        if ts: first = first or ts; last = ts
        m = d.get("message")
        if isinstance(m, dict):
            model = model or m.get("model")
            c = m.get("content")
            if isinstance(c, list):
                tools += sum(1 for b in c if isinstance(b, dict) and b.get("type") == "tool_use")
            mid = m.get("id")   # absent on some synthetic/older records -> can't dedup, always count
            if mid is None or mid not in seen_msg_ids:
                if mid is not None: seen_msg_ids.add(mid)
                u = m.get("usage") or {}
                out_tok     += u.get("output_tokens") or 0
                in_tok      += u.get("input_tokens") or 0
                cache_w_tok += u.get("cache_creation_input_tokens") or 0
                cache_r_tok += u.get("cache_read_input_tokens") or 0
    return dict(records=rec, tools=tools, out_tok=out_tok, in_tok=in_tok,
                cache_w_tok=cache_w_tok, cache_r_tok=cache_r_tok, first=first, last=last, model=model)

def tooluse_ids(path):
    ids = []
    for d in read_jsonl(path):
        m = d.get("message")
        c = m.get("content") if isinstance(m, dict) else None
        if isinstance(c, list):
            ids += [b.get("id") for b in c if isinstance(b, dict) and b.get("type") == "tool_use"]
    return ids

def build_model(root, run_id, session_override=None):
    sess = resolve_sessions(root, run_id, session_override)
    agents, tu_owner, l0 = {}, {}, []
    for s in sess:
        sid = s["session_id"]
        main, subdir = session_paths(root, run_id, s)
        l0.append((sid, main))
        if main:
            for tid in tooluse_ids(main): tu_owner[tid] = ("L0", sid)
        if os.path.isdir(subdir):
            for jp in glob.glob(os.path.join(subdir, "agent-*.jsonl")):
                aid = os.path.basename(jp)[len("agent-"):-len(".jsonl")]
                meta = {}
                mp = jp[:-len(".jsonl")] + ".meta.json"
                if os.path.exists(mp):
                    try: meta = json.load(open(mp))
                    except Exception: pass
                agents[aid] = {"agent_id": aid, "session": sid, "jsonl": jp, "meta": meta, **jsonl_stats(jp)}
                for tid in tooluse_ids(jp): tu_owner[tid] = aid
    for aid, a in agents.items():
        a["parent"] = tu_owner.get((a["meta"] or {}).get("toolUseId"))
    sem = {}                                                            # semantic tags from run-events (agent_id join)
    for e in load_events(root):
        aid = e.get("agent_id")
        if aid and e.get("event") in ("agent_spawn", "agent_return"):
            sem.setdefault(aid, {}).update({k: e[k] for k in ("role", "paper", "round", "status") if e.get(k) is not None})
    for aid, a in agents.items():
        a["sem"] = sem.get(aid, {})
    return l0, agents

def label(a):
    meta, sem = a.get("meta") or {}, a.get("sem") or {}
    role = sem.get("role") or meta.get("agentType") or "?"
    desc = (meta.get("description") or "").replace("\n", " ")[:58]
    tag  = " ".join(f"{k}={sem[k]}" for k in ("paper", "round", "status") if sem.get(k) is not None)
    return (f"[{role}] {desc}  · {a['records']}rec/{a['tools']}tools/{a['out_tok']//1000}k · {a['agent_id'][:12]}"
            + (f" · {tag}" if tag else ""))

# ---------------------------------------------------------------- subcommands
def cmd_timeline(a):
    ev = load_events(ROOT); run_id = a.run or current_run_id(ROOT, ev)
    rows = [e for e in ev if (not run_id or e.get("run_id") == run_id) and (not a.paper or e.get("paper") == a.paper)]
    SHELL = {"ts", "run_id", "event", "paper", "round", "milestone", "stage"}
    for e in rows:
        extra = " ".join(f"{k}={e[k]}" for k in e if k not in SHELL and e[k] is not None)
        print(f"{e.get('ts')}  {str(e.get('event')):18s} p={e.get('paper')} r={e.get('round')} ms={e.get('milestone')}  {extra[:96]}")
    print(f"\n{len(rows)} event(s); run_id={run_id}")
    if not ev: print("(no run-events.jsonl yet — this run predates the event stream, or hasn't started)")

def cmd_tree(a):
    run_id = a.run or current_run_id(ROOT)
    l0, agents = build_model(ROOT, run_id, a.session)
    kids = {}
    for aid, ag in agents.items():
        p = ag["parent"]
        key = p if (isinstance(p, tuple) or p in agents) else None
        kids.setdefault(key, []).append(aid)
    def walk(key, depth):
        for aid in sorted(kids.get(key, []), key=lambda x: agents[x].get("first") or ""):
            print("   " * depth + "└─ " + label(agents[aid])); walk(aid, depth + 1)
    if not l0: print("no sessions resolved (set --session SID or run from a real run)"); return
    for sid, _ in l0:
        print(f"L0 session {sid}" + (f"  ·  run {run_id}" if run_id else "")); walk(("L0", sid), 1)
    placed = set()
    def collect(k):
        for aid in kids.get(k, []): placed.add(aid); collect(aid)
    for sid, _ in l0: collect(("L0", sid))
    orph = [aid for aid in agents if aid not in placed]
    if orph:
        print("\n(unlinked — spawning tool_use not in harvested sessions, e.g. cross-session parent:)")
        for aid in orph: print("   • " + label(agents[aid]))
    print(f"\n{len(agents)} agent(s) across {len(l0)} session(s).")

def cmd_agent(a):
    run_id = a.run or current_run_id(ROOT)
    _, agents = build_model(ROOT, run_id, a.session)
    match = [k for k in agents if k == a.agent_id or k.startswith(a.agent_id)]
    if not match:
        print(f"no agent matching '{a.agent_id}'. known: " + ", ".join(list(agents)[:12])); return
    ag = agents[match[0]]; meta = ag["meta"] or {}
    print(f"agent {ag['agent_id']}  [{meta.get('agentType')}]  {meta.get('description')}")
    print(f"  session={ag['session']}  records={ag['records']} tools={ag['tools']}  "
          f"tokens: in={ag['in_tok']} cache_w={ag['cache_w_tok']} cache_r={ag['cache_r_tok']} out={ag['out_tok']}  "
          f"model={ag['model']}")
    print(f"  parent={ag['parent']}  sem={ag['sem']}")
    print("  --- action trace (tool calls + text) ---")
    for d in read_jsonl(ag["jsonl"]):
        ts = (d.get("timestamp") or "")[11:19]; role = d.get("type"); m = d.get("message")
        c = m.get("content") if isinstance(m, dict) else m
        if isinstance(c, list):
            for b in c:
                if not isinstance(b, dict): continue
                t = b.get("type")
                if t == "text":
                    txt = (b.get("text") or "").strip().replace("\n", " ")
                    if txt: print(f"  {ts} {role:9s} {txt[:150]}")
                elif t == "tool_use":
                    print(f"  {ts} TOOL→     {b.get('name')}({json.dumps(b.get('input', {}), ensure_ascii=False)[:120]})")
                elif t == "tool_result":
                    rc = b.get("content"); s = rc if isinstance(rc, str) else json.dumps(rc, ensure_ascii=False)
                    print(f"  {ts} result    {str(s)[:150]}")
        elif isinstance(c, str) and c.strip():
            print(f"  {ts} {role:9s} {c.strip()[:150]}")

def cmd_attribute(a):
    run_id = a.run or current_run_id(ROOT)
    l0, agents = build_model(ROOT, run_id, a.session)
    pat = re.compile(a.pattern)
    targets = [(aid, ag["jsonl"], ag) for aid, ag in agents.items()]
    for sid, main in l0:
        if main and os.path.exists(main): targets.append((f"L0:{sid}", main, None))
    hits = 0
    for name, path, ag in targets:
        for d in read_jsonl(path):
            blob = json.dumps(d.get("message", d), ensure_ascii=False)
            mm = pat.search(blob)
            if mm:
                ts = (d.get("timestamp") or "")[:19]
                ctx = blob[max(0, mm.start() - 40):mm.end() + 40].replace("\n", " ")
                who = (ag["sem"].get("role") if ag and ag.get("sem") else None) or (ag["meta"].get("agentType") if ag else "L0")
                desc = (ag["meta"].get("description") if ag else "main session") or ""
                print(f"{name[:14]:14s} [{who}] {desc[:42]}  @{ts}\n    …{ctx}…")
                hits += 1; break
    print(f"\n{hits} agent/transcript(s) contain /{a.pattern}/  (run_id={run_id})")

def cmd_health(a):
    root = ROOT; ev = load_events(root); run_id = a.run or current_run_id(root, ev)
    out = []
    def red(code, msg): out.append(("RED", code, msg))
    # ---- event-based (next run; precise) ----
    rounds_verdict, reviewer = {}, {}
    for e in ev:
        ets = e.get("event")
        if ets == "envelope_invalid":                                   red("RC-3", f"envelope_invalid role={e.get('role')} @{e.get('ts')}")
        if ets == "gate_input_derived" and e.get("mismatch"):           red("RC-4", f"gate-input MISMATCH paper={e.get('paper')} round={e.get('round')}")
        if ets == "orphan_stop_scan" and (e.get("new") or 0) > 0:       red("seam", f"orphan stop markers new={e.get('new')} paper={e.get('paper')} round={e.get('round')}")
        if ets == "hook_unarmed":                                       red("RC-6", f"fidelity hook UNARMED paper={e.get('paper')} round={e.get('round')} where={e.get('where')}")
        if ets == "verdict":                                            rounds_verdict[(e.get("paper"), e.get("round"))] = e
        if ets == "agent_return" and e.get("role") == "review_orchestrator":
            reviewer[(e.get("paper"), e.get("round"))] = e.get("subagents_spawned")
    for key, v in rounds_verdict.items():
        sp = reviewer.get(key)
        if sp is None:  red("RC-2", f"verdict for paper={key[0]} round={key[1]} but NO review_orchestrator return recorded")
        elif sp == 0:   red("RC-2", f"review_orchestrator paper={key[0]} round={key[1]} subagents_spawned=0 (no real panel)")
    # ---- artifact-based (works on legacy runs too) ----
    for ms_path in sorted(glob.glob(os.path.join(root, "runs", "*", "milestone-state.json"))):
        slug = os.path.basename(os.path.dirname(ms_path))
        if a.paper and a.paper != slug: continue
        try: ms = json.load(open(ms_path))
        except Exception: continue
        for k, v in (ms.get("milestones") or {}).items():
            if isinstance(v, dict) and v.get("completed_at") and not (v.get("code_commit") or v.get("paper_commit")):
                red("RC-9", f"{slug}:{k} completed but NO commit recorded in milestone-state")
        done = any((isinstance(v, dict) and v.get("completed_at")) or v == "completed" for v in (ms.get("milestones") or {}).values())
        for repo in ("code", "paper"):
            rp = os.path.join(root, "runs", slug, repo)
            if os.path.isdir(os.path.join(rp, ".git")) and done:
                try:
                    r = subprocess.run(["git", "-C", rp, "rev-list", "--count", "HEAD"], capture_output=True, text=True)
                    if r.returncode != 0 or r.stdout.strip() in ("", "0"):
                        red("RC-9", f"{slug}/{repo} provenance repo has NO commits though milestones claim done")
                except Exception: pass
    for gp in sorted(glob.glob(os.path.join(root, "runs", "*", "loop-gate-input-r*.json"))):
        try: g = json.load(open(gp))
        except Exception: continue
        if a.paper and a.paper not in gp: continue
        if g.get("mismatch"): red("RC-4", f"{os.path.relpath(gp, root)}: derived≠claimed (envelope under-reported a disk change)")
    # ---- trace-based: NO forbidden built-in subagent type ever spawned (RC-13) ----
    # 'general-purpose' is the harness catch-all: it carries the Agent tool and can recurse into an unbounded
    # nested spawn tree. The spawn_guard PreToolUse hook DENIES it at the top level, but a general-purpose spawned
    # BY a subagent (nested) is not reliably intercepted — so this post-hoc trace audit is the deterministic
    # backstop. Every auto-research spawn must name an explicit non-nesting type (auto-research:leaf-worker / a
    # namespaced vendored leaf); a blank subagent_type silently resolves to general-purpose, which this catches.
    traced_gp = 0
    try:
        _, agents = build_model(root, run_id)
        for aid, ag in agents.items():
            meta = ag.get("meta") or {}
            if meta.get("agentType") == "general-purpose":
                traced_gp += 1
                red("RC-13", f"forbidden subagent_type 'general-purpose' in trace (depth={meta.get('spawnDepth')}) "
                             f"— {(meta.get('description') or '')[:56]} · {aid[:12]}")
    except Exception:
        pass
    # ---- event-level RC-13 (P-7/X-ena-3): raw agent_spawn subagent_type straight from run-events.jsonl.
    # Transcript-independent: still fires when degraded.trace=true, and SEES spawn_guard-DENIED attempts
    # (the hook logs BEFORE its deny — hooks/spawn_guard.py — and a denied spawn never gets a transcript
    # node). BOTH views stay: only the trace sees NESTED spawns (the top-level hook never fires for them);
    # only the events survive transcript pruning and record denials. run_id filter = cmd_rollup precedent
    # (in (run_id, None)); hook records may carry a null run_id wrapper.
    notes = []
    spawn_ev = [e for e in ev if e.get("event") == "agent_spawn" and e.get("run_id") in (run_id, None)]
    ev_gp = 0
    for e in spawn_ev:
        st = str(e.get("subagent_type") or "").strip().lower()      # same normalization as spawn_guard.py:93
        desc = (e.get("description") or "")[:56]
        if st == "general-purpose":
            ev_gp += 1
            ctx = "logged-then-DENIED by spawn_guard" if e.get("src") == "hook" else f"src={e.get('src')}"
            red("RC-13", f"forbidden subagent_type 'general-purpose' in run-events ({ctx}) — {desc} @{e.get('ts')}")
        elif not st and e.get("src") == "hook":
            # blank resolves to general-purpose at the harness, but the CURRENT guard denies only the exact
            # string — a blank spawn was logged AND let through (H-3 pending). Flag it; do NOT claim a deny.
            ev_gp += 1
            red("RC-13", f"blank subagent_type in run-events (resolves to 'general-purpose'; NOT denied by current spawn_guard) — {desc} @{e.get('ts')}")
    if ev_gp:
        notes.append(f"RC-13 event-level: {ev_gp} 'general-purpose' agent_spawn event(s) (top-level, denied attempts included); {traced_gp} in trace (executed, nested included)")
    elif not spawn_ev:
        notes.append("RC-13 (event-level) skipped: no agent_spawn events in run-events.jsonl to scan; transcript-based RC-13 still ran")
    # ---- report ----
    reds = [f for f in out if f[0] == "RED"]
    for lvl, code, msg in out: print(f"🔴 [{code}] {msg}")
    if not out: print("🟢 no flags raised by the checks that have data")
    src = f"events={len(ev)}"
    print(f"\n{'❌ ' + str(len(reds)) + ' red flag(s)' if reds else '✅ clean'}  ·  run_id={run_id}  ·  {src}")
    for n in notes: print(f"({n})")
    if not ev:
        print("(no run-events.jsonl — event-based RC-1/2/3/6 + seam checks skipped; artifact RC-4/9 still ran)")

def cmd_rollup(a):
    """Machine-readable per-run totals — tokens/models per role (from transcripts), spawns per stage,
    gate open->answer spans, detach stats (from events). Derived on demand; nothing persisted unless --out."""
    root = ROOT; ev = load_events(root); run_id = a.run or current_run_id(root, ev)
    run_ev = [e for e in ev if e.get("run_id") in (run_id, None)]
    l0, agents = build_model(root, run_id, a.session)
    TOK_KEYS = ("out_tok", "in_tok", "cache_w_tok", "cache_r_tok")
    by_role, by_model = {}, {}
    tot = {k: 0 for k in TOK_KEYS}; tot.update(tools=0, records=0)

    def add(role, model, stats):
        r = by_role.setdefault(role, {"agents": 0, "tools": 0, "models": {}, **{k: 0 for k in TOK_KEYS}})
        r["agents"] += 1; r["tools"] += stats.get("tools", 0)
        for k in TOK_KEYS: r[k] += stats.get(k, 0)
        r["models"][model] = r["models"].get(model, 0) + 1
        bm = by_model.setdefault(model, {"agents": 0, **{k: 0 for k in TOK_KEYS}})
        bm["agents"] += 1
        for k in TOK_KEYS: bm[k] += stats.get(k, 0)
        tot["tools"] += stats.get("tools", 0); tot["records"] += stats.get("records", 0)
        for k in TOK_KEYS: tot[k] += stats.get(k, 0)

    # L0 (the orchestrator's own turns) — a separate role bucket, folded in from EVERY native session
    # this run touched (a run can span more than one <uuid>.jsonl across detach/rewake or a terminal
    # reopen; state/sessions.jsonl + resolve_sessions() already stitch them together for this run_id).
    for sid, main in l0:
        if main and os.path.exists(main):
            stats = jsonl_stats(main)
            add("L0", stats.get("model") or "?", stats)

    for ag in agents.values():
        role = (ag.get("sem") or {}).get("role") or (ag.get("meta") or {}).get("agentType") or "?"
        add(role, ag.get("model") or "?", ag)
    stage_spans, spawns_by_stage = {}, {}
    gates = {"opened": 0, "answered": 0, "archived": 0, "by_id": {}}
    detached = {"long_run_fired": 0, "finalized": 0, "anomalies": 0, "crashes": 0, "rewakes": 0}
    first_ts = last_ts = None
    for e in run_ev:
        ts = e.get("ts")
        if ts: first_ts = first_ts or ts; last_ts = ts
        st = e.get("stage") or "?"
        ss = stage_spans.setdefault(st, {"first": ts, "last": ts, "events": 0})
        ss["last"] = ts or ss["last"]; ss["events"] += 1
        evn = e.get("event")
        if evn == "agent_spawn" and e.get("src") != "hook":
            spawns_by_stage[st] = spawns_by_stage.get(st, 0) + 1
        elif evn == "gate_open":   gates["opened"] += 1;  gates["by_id"].setdefault(e.get("id") or "?", {})["opened"] = ts
        elif evn == "gate_answer": gates["answered"] += 1; gates["by_id"].setdefault(e.get("id") or "?", {})["answered"] = ts
        elif evn == "decision_archived": gates["archived"] += 1
        elif evn == "long_run_fired":      detached["long_run_fired"] += 1
        elif evn == "detached_finalized":  detached["finalized"] += 1
        elif evn == "detached_anomaly":    detached["anomalies"] += 1
        elif evn == "detached_crash":      detached["crashes"] += 1
        elif evn == "rewake":              detached["rewakes"] += 1
    out = {"schema": "auto-research-rollup@2", "run_id": run_id,
           "inputs": {"events": len(run_ev), "l0_sessions": len(l0), "agent_transcripts": len(agents)},
           "totals": tot, "by_role": by_role, "by_model": by_model,
           "spawns_by_stage": spawns_by_stage, "stage_spans": stage_spans,
           "wall": {"first_ts": first_ts, "last_ts": last_ts},
           "gates": gates, "detached": detached,
           "caveats": ["in_tok/cache_w_tok/cache_r_tok/out_tok are input_tokens/cache_creation_input_tokens/"
                       "cache_read_input_tokens/output_tokens from message.usage, deduped by message.id "
                       "(one API response can split into several JSONL lines that repeat the same usage)",
                       "totals/by_role now include an 'L0' bucket for the orchestrator's own turns, "
                       "in addition to L1/L2 subagent transcripts (schema@1 counted subagents only)",
                       "token/model stats exist only while transcripts survive (snapshot or live)"]}
    js = json.dumps(out, ensure_ascii=False, indent=1)
    if getattr(a, "out", None):
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w") as f: f.write(js + "\n")
    print(js)

def main():
    ap = argparse.ArgumentParser(prog="run_report.py", description="read-only attribution reader for an auto-research run")
    sub = ap.add_subparsers(dest="cmd")
    for n in ("timeline", "health"):
        p = sub.add_parser(n); p.add_argument("--paper"); p.add_argument("--run")
    pt = sub.add_parser("tree"); pt.add_argument("--run"); pt.add_argument("--session")
    pa = sub.add_parser("agent"); pa.add_argument("agent_id"); pa.add_argument("--run"); pa.add_argument("--session")
    px = sub.add_parser("attribute"); px.add_argument("pattern"); px.add_argument("--run"); px.add_argument("--session")
    pr = sub.add_parser("rollup"); pr.add_argument("--run"); pr.add_argument("--session"); pr.add_argument("--out")
    a = ap.parse_args()
    {"timeline": cmd_timeline, "tree": cmd_tree, "agent": cmd_agent,
     "attribute": cmd_attribute, "health": cmd_health, "rollup": cmd_rollup}.get(a.cmd, lambda _: ap.print_help())(a)

if __name__ == "__main__":
    main()
