#!/usr/bin/env python3
r"""paper-polish — provenance run-ledger for the /review supplementary-experiment phase.

The mechanical half of the experiment phase: the orchestrator runs experiments through THIS tool so
the proof (timestamps, hashes, git-status, captured stdout) is minted outside any agent's transcript.
The experimenter/run-auditor roles call these subcommands (see skills/experiment-run + run-audit); the "how" lives in the skills.

Subcommands (all operate on a single ledger JSON file):

  init    --ledger L --repo R --project P
          Create an empty ledger {schema, project_dir, experiment_repo, runs:[]} (idempotent).

  run     --ledger L --repo R --ledger-id ID --punch-item PID --cmd 'CMD' --logdir D
          [--products a,b]  [--results PATH]  [--extract 'tok=path;tok2=path']  [--env 'K=V,K2=V2']
          Stamp started; capture each product's BEFORE state (git ls-files / git show HEAD sha);
          run CMD via the shell, tee stdout+stderr to D/ID.stdout.log; stamp finished; capture AFTER
          state (git status, sha256, mtime); extract numbers from --results by --extract field paths;
          append an audit_status:"pending" record. Prints the record JSON. Exit 0 even if CMD failed
          (the record carries exit_code; the auditor judges).

  record  --ledger L --repo R --ledger-id ID --punch-item PID --cmd 'CMD' --logdir D --stdout-log LOG
          [--products a,b]  [--results PATH]  [--extract 'tok=path;…']
          POST-HOC record of a run the EXPERIMENTER already executed itself at full scale (short tiers).
          No subprocess is launched: mint provenance from DISK so the independent auditor can re-derive
          it — capture each product's AFTER state (git status, sha256 vs HEAD, mtime), extract numbers
          from --results, and copy + hash the experimenter's tee'd stdout LOG. started_at is null (the
          experimenter ran it); freshness rests on git-sha-changed + the results-JSON's own timestamp +
          the stdout log (health + the experiment's DISCRIMINATIVE sanity self-check). audit_status
          "pending". Prints the record JSON.

  run-detach --ledger L --repo R --ledger-id ID --cmd 'CMD' --logdir D --pidfile P
          [--products …] [--results …] [--extract …] [--env …] [--punch-item PID]
          Like `run`, but FIRE-AND-FORGET for a long local job: capture each product's BEFORE state,
          launch CMD in a NEW SESSION (survives this process exiting), tee stdout to D/ID.stdout.log,
          and append the child PID to the PIDFILE P (the asyncRewake Stop hook OS-waits on it — a
          zero-token wait — and exit-2 re-wakes the session when it finishes). A wrapper writes the
          exit code to D/ID.exitcode on completion. Records run_status:"running"; returns {ledger_id,
          pid, run_status}. The AFTER state is captured later by `finalize`.

  finalize --ledger L --ledger-id ID
          Called on the re-wake: read the exitcode file, capture the AFTER state (git-status, sha256,
          mtime), extract numbers from the results file, hash the stdout, and complete the record
          (run_status:"finished", audit_status stays "pending"). Prints the completed record JSON.
          A no-op (prints the record) for a non-detached run.

  status  --ledger L --ledger-id ID
          Single (non-looping) check of a detached run: prints {run_status:"running"|"finished"}.

  set-audit --ledger L --ledger-id ID --status pass|fail [--report @file|'json']
          Set audit_status + audit_report on a record (the orchestrator writes the auditor's verdict).

  bless   --ledger L --manifest M --ledger-id ID
          [--swaps 'old=>new=>file;…']  [--files 'path;…']
          ONLY if the record is audit_status=="pass": append blessed_numbers / blessed_files entries
          (each tagged with ledger_id) to the experiment manifest M, so the pre-edit hook will permit
          exactly those write-backs. Refuses on a non-passed record (fail-closed).

  register --ledger L --ledger-id ID --registry REG  [--phase B1|B2]  [--require-audit]
          Append the record's extracted_numbers (+ provenance: ledger_path, results_file/field, command,
          commit_sha, stdout sha, audit_status, phase) to the FORWARD-CARRIED audited-values registry REG
          (schema auto-research/audited-values@1) — the single paper-facing index a downstream provenance
          auditor (/rewrite) looks numbers up in instead of re-deriving from scratch. Append-only +
          idempotent (dedup by ledger_id+quantity+value); creates REG if absent. --require-audit registers
          ONLY an audit_status=="pass" record (B2's independently-audited path); omit for B1 self-review.

A field path is dotted with optional [index]: e.g. `results[3].solve_seconds`, `kappa.Ni`.
"""

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def git(repo, *args):
    try:
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True).stdout
    except Exception:
        return ""


def git_blob_sha(repo, relpath):
    """sha256 of HEAD:relpath (pre-run content), or None if untracked/absent."""
    try:
        p = subprocess.run(["git", "-C", repo, "show", f"HEAD:{relpath}"],
                           capture_output=True)
        if p.returncode != 0:
            return None
        return hashlib.sha256(p.stdout).hexdigest()
    except Exception:
        return None


def rel(repo, path):
    try:
        return os.path.relpath(os.path.abspath(path), os.path.abspath(repo))
    except Exception:
        return path


def load(path):
    with open(path) as f:
        return json.load(f)


def save(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def resolve_path(obj, path):
    """Navigate a dotted path with [index] segments. Returns the value or raises KeyError/IndexError."""
    cur = obj
    for tok in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if tok.startswith("[") and tok.endswith("]"):
            cur = cur[int(tok[1:-1])]
        else:
            cur = cur[tok]
    return cur


# --- shared capture helpers (used by both `run` and the detached `run-detach`/`finalize` pair) ---

def parse_env(env_str):
    env_overrides = {}
    if env_str:
        for kv in env_str.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                env_overrides[k.strip()] = v.strip()
    return env_overrides


def capture_before(repo, products):
    before = {}
    for p in products:
        r = rel(repo, p)
        tracked = bool(git(repo, "ls-files", "--", r).strip())
        before[p] = {
            "rel": r,
            "git_status_before": "tracked" if tracked else "absent",
            "sha256_before": git_blob_sha(repo, r) if tracked else None,
        }
    return before


def capture_after(repo, products, before):
    prod_records = []
    for p in products:
        b = before.get(p) or {"rel": rel(repo, p), "git_status_before": "absent", "sha256_before": None}
        r = b["rel"]
        st = git(repo, "status", "--short", "--", r).strip()
        if st.startswith("??"):
            status_after = "untracked"
        elif st:
            status_after = "modified"
        else:
            status_after = "unchanged"
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(p), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            mtime = None
        prod_records.append({
            "path": os.path.abspath(p),
            "rel": r,
            "role": "results" if p.endswith(".json") else ("figure" if re.search(r"\.(pdf|png|svg)$", p) else "other"),
            "git_status_before": b["git_status_before"],
            "git_status_after": status_after,
            "sha256_before": b["sha256_before"],
            "sha256_after": sha256_file(p),
            "mtime_after": mtime,
        })
    return prod_records


def do_extract(results_path, products, extract_spec):
    extracted = []
    rp = results_path or next((p for p in products if p.endswith(".json")), None)
    data = None
    if rp and os.path.isfile(rp):
        try:
            data = load(rp)
        except Exception:
            data = None
    if extract_spec and data is not None:
        for pair in extract_spec.split(";"):
            if "=" not in pair:
                continue
            tok, fp = pair.split("=", 1)
            tok, fp = tok.strip(), fp.strip()
            try:
                val = resolve_path(data, fp)
                extracted.append({"token": tok, "value": str(val), "source": fp, "as_written": str(val)})
            except Exception as e:
                extracted.append({"token": tok, "value": None, "source": fp, "error": f"{type(e).__name__}: {e}"})
    return extracted


def read_log(log_path):
    try:
        with open(log_path, "rb") as lf:
            raw = lf.read()
    except Exception:
        raw = b""
    sha = hashlib.sha256(raw).hexdigest()
    tail = "\n".join(raw.decode("utf-8", "ignore").splitlines()[-40:])
    return sha, tail


def upsert(led_path, record):
    led = load(led_path)
    led["runs"] = [r for r in led.get("runs", []) if r.get("ledger_id") != record["ledger_id"]]
    led["runs"].append(record)
    save(led_path, led)


def find_run(led, ledger_id):
    return next((r for r in led.get("runs", []) if r.get("ledger_id") == ledger_id), None)


# ---------------------------------------------------------------------------

def cmd_init(a):
    if os.path.isfile(a.ledger):
        return
    os.makedirs(os.path.dirname(a.ledger) or ".", exist_ok=True)
    save(a.ledger, {
        "schema": "paper-polish/run-ledger@1",
        "project_dir": a.project,
        "experiment_repo": a.repo,
        "runs": [],
    })


def cmd_run(a):
    repo = a.repo
    products = [p for p in (a.products.split(",") if a.products else []) if p.strip()]
    env_overrides = parse_env(a.env)

    started = now_iso()
    before = capture_before(repo, products)

    # RUN (CMD already carries any cd/bash -lc wrapping; tee to log)
    os.makedirs(a.logdir, exist_ok=True)
    log_path = os.path.join(a.logdir, f"{a.ledger_id}.stdout.log")
    with open(log_path, "wb") as lf:
        proc = subprocess.run(a.cmd, shell=True, stdout=lf, stderr=subprocess.STDOUT)
    exit_code = proc.returncode
    finished = now_iso()

    prod_records = capture_after(repo, products, before)
    results_path = a.results or next((p for p in products if p.endswith(".json")), None)
    extracted = do_extract(results_path, products, a.extract)
    stdout_sha, tail = read_log(log_path)

    record = {
        "ledger_id": a.ledger_id,
        "punch_item_id": a.punch_item,
        "command": a.cmd,
        "cwd": repo,
        "env_overrides": env_overrides,
        "exit_code": exit_code,
        "started_at": started,
        "finished_at": finished,
        "stdout_log": os.path.abspath(log_path),
        "stdout_sha256": stdout_sha,
        "stdout_tail": tail,
        "products": prod_records,
        "extracted_numbers": extracted,
        "detached": False,
        "run_status": "finished",
        "audit_status": "pending",
        "audit_report": None,
    }
    upsert(a.ledger, record)
    print(json.dumps(record, indent=2))


def cmd_record(a):
    """Post-hoc record of a run the experimenter already executed itself (short tiers, INV-4 option b).

    No subprocess is launched. Provenance is minted from DISK (git status / sha256 vs HEAD / mtime) +
    the experimenter's tee'd stdout log (copied into logdir + hashed), so the INDEPENDENT auditor can
    re-derive it. started_at is null; freshness rests on git-sha-changed + the results-JSON's own
    timestamp + the stdout log's health and the experiment's DISCRIMINATIVE sanity self-check.
    """
    repo = a.repo
    products = [p for p in (a.products.split(",") if a.products else []) if p.strip()]
    # HEAD blob shas are unaffected by the experimenter's working-tree run, so capturing BEFORE now still
    # yields the pre-run committed content — the sha-changed freshness check stays valid.
    before = capture_before(repo, products)
    prod_records = capture_after(repo, products, before)
    results_path = a.results or next((p for p in products if p.endswith(".json")), None)
    extracted = do_extract(results_path, products, a.extract)

    # copy the experimenter's tee'd stdout into the canonical logdir path, then hash it (the auditor
    # re-reads it + checks the sha + the sanity self-check). The copy preserves the bytes, so the sha holds.
    os.makedirs(a.logdir, exist_ok=True)
    canon_log = os.path.join(a.logdir, f"{a.ledger_id}.stdout.log")
    log_path = None
    if a.stdout_log and os.path.isfile(a.stdout_log):
        try:
            if os.path.abspath(a.stdout_log) != os.path.abspath(canon_log):
                shutil.copyfile(a.stdout_log, canon_log)
            log_path = canon_log
        except Exception:
            log_path = a.stdout_log
    stdout_sha, tail = read_log(log_path) if log_path else (None, None)
    # best-available timestamp: when the experimenter wrote the stdout log (the run window is the
    # experimenter's, not the orchestrator's — there is no minted [started, finished] window here).
    try:
        finished = datetime.fromtimestamp(os.path.getmtime(log_path), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if log_path else now_iso()
    except Exception:
        finished = now_iso()

    record = {
        "ledger_id": a.ledger_id,
        "punch_item_id": a.punch_item,
        "command": a.cmd,
        "cwd": repo,
        "env_overrides": parse_env(a.env),
        "exit_code": None,                  # the experimenter ran it; run-health is judged from the stdout log + the sanity self-check
        "started_at": None,                 # no orchestrator-minted window for a post-hoc record
        "finished_at": finished,
        "recorded_at": now_iso(),
        "stdout_log": os.path.abspath(log_path) if log_path else None,
        "stdout_sha256": stdout_sha,
        "stdout_tail": tail,
        "products": prod_records,
        "extracted_numbers": extracted,
        "detached": False,
        "ran_by": "experimenter",           # the experimenter executed the real config; the orchestrator recorded it post-hoc
        "run_status": "finished",
        "audit_status": "pending",
        "audit_report": None,
    }
    upsert(a.ledger, record)
    print(json.dumps(record, indent=2))


def cmd_run_detach(a):
    """Fire a long local run in the background and append its PID to the PIDFILE.

    The job runs in a NEW SESSION so it survives this process (and the Claude turn) ending. A wrapper
    writes the exit code to <logdir>/<id>.exitcode on completion; `finalize` reads it on the re-wake.
    The AFTER state is NOT captured here (the run is still going) — only the BEFORE state + the run spec
    are stashed in the record so finalize can complete it deterministically.
    """
    repo = a.repo
    products = [p for p in (a.products.split(",") if a.products else []) if p.strip()]
    env_overrides = parse_env(a.env)

    started = now_iso()
    before = capture_before(repo, products)

    os.makedirs(a.logdir, exist_ok=True)
    log_path = os.path.join(a.logdir, f"{a.ledger_id}.stdout.log")
    exitcode_path = os.path.join(a.logdir, f"{a.ledger_id}.exitcode")
    try:
        os.remove(exitcode_path)
    except OSError:
        pass

    # the command cds itself; the wrapper records the exit code so finalize can read it post-rewake.
    wrapper = f"{a.cmd}; printf '%s' \"$?\" > {shlex.quote(exitcode_path)}"
    lf = open(log_path, "wb")
    proc = subprocess.Popen(["sh", "-c", wrapper], stdout=lf, stderr=subprocess.STDOUT,
                            start_new_session=True)
    pid = proc.pid

    # record the PID for the asyncRewake Stop hook (it OS-waits on these — a zero-token wait).
    os.makedirs(os.path.dirname(a.pidfile) or ".", exist_ok=True)
    with open(a.pidfile, "a") as pf:
        pf.write(f"{pid}\n")

    record = {
        "ledger_id": a.ledger_id,
        "punch_item_id": a.punch_item,
        "command": a.cmd,
        "cwd": repo,
        "env_overrides": env_overrides,
        "exit_code": None,
        "started_at": started,
        "finished_at": None,
        "stdout_log": os.path.abspath(log_path),
        "stdout_sha256": None,
        "stdout_tail": None,
        "products": [],
        "extracted_numbers": [],
        "detached": True,
        "pid": pid,
        "run_status": "running",
        "audit_status": "pending",
        "audit_report": None,
        # finalize-only scratch (stripped once the record is completed):
        "_exitcode_path": exitcode_path,
        "_before": before,
        "_products": products,
        "_results": a.results or "",
        "_extract": a.extract or "",
    }
    upsert(a.ledger, record)
    print(json.dumps({"ledger_id": a.ledger_id, "pid": pid, "run_status": "running",
                      "stdout_log": os.path.abspath(log_path)}, indent=2))


def cmd_finalize(a):
    led = load(a.ledger)
    rec = find_run(led, a.ledger_id)
    if not rec:
        sys.exit(f"ledger_id {a.ledger_id} not found")
    if not rec.get("detached"):
        print(json.dumps(rec, indent=2))   # already complete (synchronous run)
        return
    exitcode_path = rec.get("_exitcode_path")
    if not exitcode_path or not os.path.isfile(exitcode_path):
        sys.exit(f"detached run {a.ledger_id} has not finished yet (no exitcode file)")
    try:
        exit_code = int((open(exitcode_path).read().strip() or "-1"))
    except Exception:
        exit_code = -1
    repo = rec.get("cwd")
    products = rec.get("_products") or []
    before = rec.get("_before") or {}
    prod_records = capture_after(repo, products, before)
    extracted = do_extract(rec.get("_results") or None, products, rec.get("_extract") or "")
    stdout_sha, tail = read_log(rec.get("stdout_log"))
    # [[MECH]] H3 (Doc C §1.1 — commit-at-finalize=A, 2026-06-18) — ATOMIC commit-on-finalize. When L0 passes
    # --commit-msg, commit the run's products into the run repo BEFORE the record is marked "finished", so a
    # crash can never strand a finalized-but-uncommitted experiment (finalized ⟺ committed; the resume's
    # finalized-skip then never abandons a real result). If the commit GENUINELY fails we sys.exit WITHOUT
    # saving — the record stays "running" so the next re-wake's finalize retries (capture_after + a "nothing to
    # commit" tolerance make the retry idempotent). The recorded commit_sha is also H2's revert anchor (闭合② —
    # the coordinated rollback target must include the latest run's <ws>/code sha, not just the milestone sha).
    # The subject is L0's draft-class "milestone <ms> run <id>:" (render_diff_ladder-safe). Absent --commit-msg =
    # capture-only (back-compat: synchronous runs + existing callers/tests are unchanged).
    commit_sha = None
    if getattr(a, "commit_msg", "") and repo:
        rels = [pr["rel"] for pr in prod_records if pr.get("rel")]
        if rels:
            git(repo, "add", "--", *rels)
        cp = subprocess.run(["git", "-C", repo, "commit", "-m", a.commit_msg],
                            capture_output=True, text=True)
        out = (cp.stdout or "") + (cp.stderr or "")
        if cp.returncode != 0 and "nothing to commit" not in out and "no changes added" not in out:
            sys.exit(f"finalize: ATOMIC commit failed for {a.ledger_id} in {repo} "
                     f"(record left 'running' for retry — H3): {out.strip()}")
        commit_sha = git(repo, "rev-parse", "HEAD").strip() or None
    rec.update({
        "exit_code": exit_code,
        "finished_at": now_iso(),
        "stdout_sha256": stdout_sha,
        "stdout_tail": tail,
        "products": prod_records,
        "extracted_numbers": extracted,
        "run_status": "finished",
        "commit_sha": commit_sha,
    })
    for k in ("_exitcode_path", "_before", "_products", "_results", "_extract"):
        rec.pop(k, None)
    save(a.ledger, led)
    print(json.dumps(rec, indent=2))


def cmd_status(a):
    led = load(a.ledger)
    rec = find_run(led, a.ledger_id)
    if not rec:
        print(json.dumps({"ledger_id": a.ledger_id, "found": False}))
        return
    if not rec.get("detached"):
        print(json.dumps({"ledger_id": a.ledger_id, "detached": False, "run_status": rec.get("run_status", "finished")}))
        return
    ec = rec.get("_exitcode_path")
    finished = bool(ec and os.path.isfile(ec))
    print(json.dumps({"ledger_id": a.ledger_id, "detached": True, "pid": rec.get("pid"),
                      "run_status": "finished" if finished else "running"}))


def cmd_set_audit(a):
    led = load(a.ledger)
    report = None
    if a.report:
        if a.report.startswith("@"):
            report = load(a.report[1:])
        else:
            try:
                report = json.loads(a.report)
            except Exception:
                report = {"raw": a.report}
    for r in led.get("runs", []):
        if r.get("ledger_id") == a.ledger_id:
            r["audit_status"] = a.status
            r["audit_report"] = report
            save(a.ledger, led)
            print(f"set {a.ledger_id} -> {a.status}")
            return
    sys.exit(f"ledger_id {a.ledger_id} not found")


def cmd_bless(a):
    led = load(a.ledger)
    rec = next((r for r in led.get("runs", []) if r.get("ledger_id") == a.ledger_id), None)
    if not rec:
        sys.exit(f"ledger_id {a.ledger_id} not found")
    if rec.get("audit_status") != "pass":
        sys.exit(f"refusing to bless: {a.ledger_id} audit_status is {rec.get('audit_status')!r}, not 'pass'")
    man = load(a.manifest)
    man.setdefault("blessed_numbers", [])
    man.setdefault("blessed_files", [])
    if a.swaps:
        for triple in a.swaps.split(";"):
            if not triple.strip():
                continue
            parts = [p.strip() for p in triple.split("=>")]
            if len(parts) != 3:
                continue
            old, new, fpath = parts
            man["blessed_numbers"].append({
                "old": old, "new": new, "file": os.path.abspath(fpath),
                "ledger_id": a.ledger_id, "provenance": f"{a.ledger_id}:{rec.get('command','')}",
            })
    if a.files:
        for fp in a.files.split(";"):
            if fp.strip():
                man["blessed_files"].append({
                    "path": os.path.abspath(fp.strip()), "ledger_id": a.ledger_id,
                    "writer": "experimenter",
                })
    save(a.manifest, man)
    print(f"blessed for {a.ledger_id}: +{len(a.swaps.split(';')) if a.swaps else 0} number(s)")


def cmd_register(a):
    """Append this run record's extracted_numbers to the forward-carried audited-values registry.

    The registry (auto-research/audited-values@1) is the single, paper-facing index of every number this
    paper is entitled to STATE — written INCREMENTALLY at production time (B1 finalize / B2 bless), so a
    downstream provenance auditor (e.g. /rewrite) can LOOK UP a paper number's provenance instead of
    re-deriving it from scratch. Append-only + idempotent (dedup by ledger_id+quantity+value); creates the
    file if absent. Each entry keeps enough to RE-DERIVE from disk (ledger_path, results_file, results_field,
    commit_sha, stdout sha) — the registry is an INDEX, never a substitute for the auditor's disk check.
    --require-audit registers ONLY a record whose audit_status == "pass" (B2's independently-audited path,
    fail-closed); omit it for B1 (producer self-review — the entry carries the record's own audit_status +
    phase=B1, so the auditor can weight provenance strength).
    """
    led = load(a.ledger)
    rec = find_run(led, a.ledger_id)
    if not rec:
        sys.exit(f"register: ledger_id {a.ledger_id} not found in {a.ledger}")
    if a.require_audit and rec.get("audit_status") != "pass":
        # fail-closed: an un-audited record contributes nothing to the audited-values registry.
        print(json.dumps({"registered": 0,
                          "skipped_reason": f"audit_status={rec.get('audit_status')!r} != 'pass' (--require-audit)"},
                         indent=2))
        return

    if os.path.isfile(a.registry):
        reg = load(a.registry)
    else:
        os.makedirs(os.path.dirname(a.registry) or ".", exist_ok=True)
        reg = {"schema": "auto-research/audited-values@1", "project_dir": led.get("project_dir"), "values": []}
    reg.setdefault("values", [])
    # P-7 fix (dossier 02, 2026-07-07): `seen` maps the value-identity key to its INDEX in reg["values"] (not
    # just membership), so a later re-registration of an ALREADY-registered value can be told apart from a
    # genuine duplicate and UPGRADED in place — the identity key deliberately EXCLUDES audit_status/phase
    # (those are what may legitimately change between a B1 self-review registration and a B2-audited one).
    seen = {(v.get("ledger_id"), v.get("quantity"), v.get("value")): i for i, v in enumerate(reg["values"])}

    # the results product (role == "results") backs results_file, so the auditor can re-open the JSON.
    results_file = next((pr.get("path") or pr.get("rel")
                         for pr in (rec.get("products") or []) if pr.get("role") == "results"), None)
    appended = now_iso()
    added = upgraded = 0
    for en in (rec.get("extracted_numbers") or []):
        val = en.get("value")
        if val is None:                       # an extraction error — nothing real to register
            continue
        quantity = en.get("source") or en.get("token")   # the dotted field path in the results JSON
        key = (a.ledger_id, quantity, str(val))
        new_audit_status, new_phase = rec.get("audit_status"), (a.phase or None)
        if key in seen:
            existing = reg["values"][seen[key]]
            # Root cause this closes: the OLD dedup key was (ledger_id,quantity,value) alone, so a B2-audit
            # re-registration of an already-B1-registered value was silently DROPPED — provenance strength
            # froze at whatever it was first registered as (often 'pending') forever. UPGRADE the existing
            # row in place when audit_status/phase genuinely changed; a byte-identical re-registration (same
            # audit_status/phase) still adds nothing, preserving the original idempotency guarantee.
            if (existing.get("audit_status"), existing.get("phase")) != (new_audit_status, new_phase):
                existing["audit_status"] = new_audit_status; existing["phase"] = new_phase
                existing["appended_at"] = appended          # re-stamp: when the upgrade was observed
                upgraded += 1
            continue
        seen[key] = len(reg["values"])
        reg["values"].append({
            "value": str(val),
            "as_written": en.get("as_written", str(val)),
            "token": en.get("token"),
            "quantity": quantity,
            "ledger_id": a.ledger_id,
            "ledger_path": os.path.abspath(a.ledger),
            "results_file": results_file,
            "results_field": en.get("source"),
            "command": rec.get("command"),
            "commit_sha": rec.get("commit_sha"),
            "stdout_sha256": rec.get("stdout_sha256"),
            "audit_status": new_audit_status,
            "phase": new_phase,
            "appended_at": appended,
        })
        added += 1
    save(a.registry, reg)
    print(json.dumps({"registered": added, "upgraded": upgraded, "total": len(reg["values"]),
                      "registry": os.path.abspath(a.registry)}, indent=2))


def main():
    ap = argparse.ArgumentParser(description="provenance run-ledger for the experiment phase")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.add_argument("--ledger", required=True)
    p.add_argument("--repo", required=True); p.add_argument("--project", required=True)
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("run")
    for f in ("--ledger", "--repo", "--ledger-id", "--cmd", "--logdir"):
        p.add_argument(f, required=True)
    p.add_argument("--punch-item", default="")
    p.add_argument("--products", default=""); p.add_argument("--results", default="")
    p.add_argument("--extract", default="")
    p.add_argument("--env", default="")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("record")
    for f in ("--ledger", "--repo", "--ledger-id", "--logdir"):
        p.add_argument(f, required=True)
    p.add_argument("--cmd", default=""); p.add_argument("--stdout-log", default="")
    p.add_argument("--punch-item", default="")
    p.add_argument("--products", default=""); p.add_argument("--results", default="")
    p.add_argument("--extract", default=""); p.add_argument("--env", default="")
    p.set_defaults(fn=cmd_record)

    p = sub.add_parser("run-detach")
    for f in ("--ledger", "--repo", "--ledger-id", "--cmd", "--logdir", "--pidfile"):
        p.add_argument(f, required=True)
    p.add_argument("--punch-item", default="")
    p.add_argument("--products", default=""); p.add_argument("--results", default="")
    p.add_argument("--extract", default="")
    p.add_argument("--env", default="")
    p.set_defaults(fn=cmd_run_detach)

    p = sub.add_parser("finalize")
    for f in ("--ledger", "--ledger-id"):
        p.add_argument(f, required=True)
    # H3 (commit-at-finalize=A, 2026-06-18): when L0 passes --commit-msg, finalize ATOMICALLY commits the run's
    # products into the run repo as part of marking the record "finished" (finalized ⟺ committed). Absent =
    # capture-only (back-compat: existing callers/tests are unchanged).
    p.add_argument("--commit-msg", default="")
    p.set_defaults(fn=cmd_finalize)

    p = sub.add_parser("status")
    for f in ("--ledger", "--ledger-id"):
        p.add_argument(f, required=True)
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("set-audit")
    for f in ("--ledger", "--ledger-id", "--status"):
        p.add_argument(f, required=True)
    p.add_argument("--report", default="")
    p.set_defaults(fn=cmd_set_audit)

    p = sub.add_parser("bless")
    for f in ("--ledger", "--manifest", "--ledger-id"):
        p.add_argument(f, required=True)
    p.add_argument("--swaps", default=""); p.add_argument("--files", default="")
    p.set_defaults(fn=cmd_bless)

    p = sub.add_parser("register")
    for f in ("--ledger", "--ledger-id", "--registry"):
        p.add_argument(f, required=True)
    p.add_argument("--phase", default="")                       # B1 | B2 — provenance-strength tag on each entry
    p.add_argument("--require-audit", action="store_true")      # fail-closed: only register audit_status=="pass"
    p.set_defaults(fn=cmd_register)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
