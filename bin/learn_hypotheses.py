#!/usr/bin/env python3
"""bin/learn_hypotheses.py — the /learn cross-run hypothesis tracker (the self-improvement flywheel's ledger).

One hypothesis per RATIFIED proposal: what changed, what the NEXT run should observably show, and what the
next retro actually found. The tracker is the only writer-validated surface — the retro (and the owner) edit
it exclusively through `apply` patches so a malformed record can never poison the next cycle.

Statuses:  ratified-pending-build -> built -> deployed -> closed-helped | closed-no-effect | closed-hurt
           (+ untracked = two consecutive unmeasurable checks; retired = owner withdrew it)
Verdicts (per checked run): helped | no-effect | hurt | unmeasurable
Key invariant (the CACHE-DRIFT lesson): a hypothesis is only TESTABLE once status=deployed — the retro must
never claim a verdict for a run that executed pre-change code.

Usage:
  learn_hypotheses.py <file> init                  create an empty tracker (refuses to overwrite)
  learn_hypotheses.py <file> list                  one line per hypothesis (id · status · statement)
  learn_hypotheses.py <file> validate              schema-check; exit 0 valid / 2 invalid
  learn_hypotheses.py <file> apply <patch.json>    atomic batch of ops:
      {"ops":[{"op":"add","hypothesis":{...}},
              {"op":"status","id":"H-3","status":"built","commit":"abc1234"},
              {"op":"check","id":"H-3","run_id":"...","verdict":"helped","evidence":"..."},
              {"op":"retire","id":"H-3","reason":"..."}]}
Deterministic OK/ERROR lines; exit 0 ok, exit 2 refusal (schema violation / unknown id / bad transition).
stdlib only; writes are atomic (tmp + os.replace).
"""
import os, sys, json

SCHEMA = "auto-research-hypotheses@1"
STATUSES = ["ratified-pending-build", "built", "deployed",
            "closed-helped", "closed-no-effect", "closed-hurt", "untracked", "retired"]
VERDICTS = ["helped", "no-effect", "hurt", "unmeasurable"]
REQUIRED = ["id", "statement", "proposal_ref", "born_run", "expected_signal", "how_to_check", "status"]

def die(msg):
    print("ERROR learn_hypotheses: " + msg); sys.exit(2)

def load(path):
    if not os.path.isfile(path): die("no tracker file at %s (run `init` first)" % path)
    try:
        with open(path) as f: return json.load(f)
    except Exception as e:
        die("tracker is not valid JSON: %s" % e)

def save(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1); f.write("\n")
    os.replace(tmp, path)

def check_hypothesis(h, seen_ids):
    hid = h.get("id")
    if not isinstance(hid, str) or not hid.startswith("H-"):
        return "hypothesis id must be a string 'H-<n>' (got %r)" % (hid,)
    if hid in seen_ids:
        return "duplicate hypothesis id %s" % hid
    for k in REQUIRED:
        if not h.get(k):
            return "%s: missing required field '%s'" % (hid, k)
    if h["status"] not in STATUSES:
        return "%s: status %r not in %s" % (hid, h["status"], STATUSES)
    for c in h.get("checked", []):
        if c.get("verdict") not in VERDICTS:
            return "%s: checked verdict %r not in %s" % (hid, c.get("verdict"), VERDICTS)
        if not c.get("run_id") or not c.get("evidence"):
            return "%s: a checked entry needs run_id + evidence" % hid
    return None

def validate_doc(doc):
    if doc.get("schema") != SCHEMA: return "schema must be %s" % SCHEMA
    if not isinstance(doc.get("hypotheses"), list): return "hypotheses must be a list"
    seen = set()
    for h in doc["hypotheses"]:
        err = check_hypothesis(h, seen)
        if err: return err
        seen.add(h["id"])
    return None

def cmd_init(path):
    if os.path.exists(path): die("refusing to overwrite existing %s" % path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    save(path, {"schema": SCHEMA, "hypotheses": []})
    print("OK hypotheses: initialized empty tracker at %s" % path)

def cmd_list(path):
    doc = load(path)
    err = validate_doc(doc)
    if err: die(err)
    hs = doc["hypotheses"]
    open_n = sum(1 for h in hs if h["status"] in ("ratified-pending-build", "built", "deployed"))
    for h in hs:
        checks = ",".join(c["verdict"] for c in h.get("checked", [])) or "-"
        print("%-6s %-22s checks[%s]  %s" % (h["id"], h["status"], checks, h["statement"][:90]))
    print("OK hypotheses: %d total, %d open" % (len(hs), open_n))

def cmd_validate(path):
    err = validate_doc(load(path))
    if err: die(err)
    print("OK hypotheses: valid")

def cmd_apply(path, patch_path):
    doc = load(path)
    err = validate_doc(doc)
    if err: die("tracker invalid before apply: %s" % err)
    try:
        with open(patch_path) as f: patch = json.load(f)
    except Exception as e:
        die("patch is not valid JSON: %s" % e)
    ops = patch.get("ops")
    if not isinstance(ops, list) or not ops: die("patch needs a non-empty ops[] list")
    by_id = {h["id"]: h for h in doc["hypotheses"]}
    applied = []
    for i, op in enumerate(ops):
        kind = op.get("op")
        if kind == "add":
            h = op.get("hypothesis") or {}
            h.setdefault("status", "ratified-pending-build")
            h.setdefault("checked", [])
            err = check_hypothesis(h, set(by_id))
            if err: die("ops[%d] add: %s" % (i, err))
            doc["hypotheses"].append(h); by_id[h["id"]] = h
            applied.append("add %s" % h["id"])
        elif kind in ("status", "check", "retire"):
            hid = op.get("id")
            if hid not in by_id: die("ops[%d] %s: unknown hypothesis id %r" % (i, kind, hid))
            h = by_id[hid]
            if kind == "status":
                st = op.get("status")
                if st not in STATUSES: die("ops[%d] status: %r not in %s" % (i, st, STATUSES))
                h["status"] = st
                if op.get("commit"): h["commit"] = op["commit"]
                applied.append("status %s -> %s" % (hid, st))
            elif kind == "check":
                if h["status"] not in ("deployed", "untracked") and op.get("verdict") != "unmeasurable":
                    die("ops[%d] check: %s is '%s', not deployed — a run that executed pre-change code "
                        "cannot yield a verdict (record unmeasurable, or set status first)" % (i, hid, h["status"]))
                c = {k: op.get(k) for k in ("run_id", "verdict", "evidence")}
                err = check_hypothesis({**h, "checked": h.get("checked", []) + [c]}, set())
                if err and "checked" in err: die("ops[%d] check: %s" % (i, err))
                if c["verdict"] not in VERDICTS: die("ops[%d] check: bad verdict %r" % (i, c["verdict"]))
                if not c["run_id"] or not c["evidence"]: die("ops[%d] check: needs run_id + evidence" % i)
                h.setdefault("checked", []).append(c)
                applied.append("check %s %s@%s" % (hid, c["verdict"], c["run_id"]))
            else:  # retire
                h["status"] = "retired"
                if op.get("reason"): h["retired_reason"] = op["reason"]
                applied.append("retire %s" % hid)
        else:
            die("ops[%d]: unknown op %r (add|status|check|retire)" % (i, kind))
    err = validate_doc(doc)
    if err: die("tracker would be invalid after apply — refused: %s" % err)
    save(path, doc)
    for a in applied: print("OK hypotheses: " + a)
    print("OK hypotheses: applied %d op(s); %d total" % (len(applied), len(doc["hypotheses"])))

def main():
    if len(sys.argv) < 3: die("usage: learn_hypotheses.py <file> init|list|validate|apply <patch.json>")
    path, cmd = sys.argv[1], sys.argv[2]
    if cmd == "init":     cmd_init(path)
    elif cmd == "list":   cmd_list(path)
    elif cmd == "validate": cmd_validate(path)
    elif cmd == "apply":
        if len(sys.argv) < 4: die("apply needs <patch.json>")
        cmd_apply(path, sys.argv[3])
    else: die("unknown subcommand %r" % cmd)

if __name__ == "__main__":
    main()
