#!/usr/bin/env python3
"""bin/learn_quality_ledger.py — the /learn cross-run QUALITY ledger (the quality-ceiling flywheel's memory).

One record per completed run: claim-arc verdict, ambition/amplifier arc, terminal disposition, venue-bar
calibration, ideation-pool ceiling. A single retro sees one run; this ledger is where "3 of 4 runs were
诚实收窄" becomes visible — the `list`/`trend` output is the only legal cross-run evidence anchor (the
evidence pack quotes it verbatim; ≥3 same-direction points ground a Structural trend finding).

Written ONLY through `apply` patches (schema-validated, atomic) so a malformed record can never poison the
flywheel. NO numeric scores anywhere — closed categorical vocabularies aligned with the /learn charter.
Grounding rule (charter rule 5, mechanized): in every judged section, a verdict other than 'unassessed'
requires non-empty `evidence`; an all-unassessed section requires `unassessed_reason`.

Usage:
  learn_quality_ledger.py <file> init                  create an empty ledger (refuses to overwrite)
  learn_quality_ledger.py <file> list                  one summary line per run
  learn_quality_ledger.py <file> validate              schema-check; exit 0 valid / 2 invalid
  learn_quality_ledger.py <file> trend                 deterministic TREND tallies + oldest->newest ARC lines
  learn_quality_ledger.py <file> apply <patch.json>    atomic batch of ops:
      {"ops":[{"op":"record","run":{...},"if_exists":"refuse"|"amend"},
              {"op":"amend","run_id":"...","run":{<whole sections to replace>}}]}
Deterministic OK/ERROR lines; exit 0 ok, exit 2 refusal. stdlib only; writes are atomic (tmp + os.replace).
"""
import os, sys, json

SCHEMA = "auto-research-quality-ledger@1"

RECORDED_BY = ["learn-record", "backfill", "owner"]
FINAL_STATUS = ["shipped", "abandoned", "unfinished", "unknown"]
E2E = ["保真", "诚实收窄", "换题", "洗白负结果", "超证据放大", "unassessed"]
SEED_TO_CONTRACT = ["faithful", "down-leak", "up-error", "unassessed"]
AMPLIFIER_ARC = ["never-fired", "at-ceiling-credible", "at-ceiling-doubted",
                 "raise-earned", "raise-not-earned", "mixed", "unassessed"]
ROUTE = ["clean", "cap_exit", "negative_result", "over_claim", "viability_killed",
         "pre_loop_abandon", "other_abandon", "died_mid_run", "unknown"]
CRASH_CAUSE = ["env_transient", "oom", "code", "unknown", None]   # failure/transient.md closed set
COLD_VERDICT = ["reject", "major_revision", "minor_revision", "accept", "not-shipped", "unassessed"]
SIGNIFICANCE = ["clearly-above-bar", "at-bar", "competent-but-incremental", "below-bar", "unassessed", None]
DELTA = ["校准一致", "面板偏严", "面板偏松", "无法比对", "unassessed"]
SNAPSHOT = ["present", "partial", "absent-expired", "absent-pre-upgrade"]
CEILING = ["池顶已选", "池顶被埋", "全池皆弱", "证据过期", "unassessed"]

TOP_KEYS = {"run_id", "slug", "recorded_at", "recorded_by", "retro_ref", "run_facts",
            "claim_arc", "ambition", "terminal", "venue_bar", "ideation_pool", "notes"}
REQUIRED_TOP = ["run_id", "recorded_at", "recorded_by", "run_facts",
                "claim_arc", "ambition", "terminal", "venue_bar", "ideation_pool"]
# section -> (allowed keys, {field: enum}, verdict fields the grounding rule watches, count fields)
SECTIONS = {
    "run_facts": ({"final_status", "exit_reason", "loop_rounds", "venue"},
                  {"final_status": FINAL_STATUS}, [], ["loop_rounds"]),
    "claim_arc": ({"end_to_end_verdict", "evidence", "unassessed_reason"},
                  {"end_to_end_verdict": E2E}, ["end_to_end_verdict"], []),
    "ambition": ({"seed_to_contract", "amplify_rounds", "raised_rounds", "at_ceiling_rounds",
                  "amplifier_arc", "evidence", "unassessed_reason"},
                 {"seed_to_contract": SEED_TO_CONTRACT, "amplifier_arc": AMPLIFIER_ARC},
                 ["seed_to_contract", "amplifier_arc"],
                 ["amplify_rounds", "raised_rounds", "at_ceiling_rounds"]),
    "terminal": ({"route", "outcome", "cause", "evidence"},
                 {"route": ROUTE, "outcome": FINAL_STATUS, "cause": CRASH_CAUSE}, [], []),
    "venue_bar": ({"cold_verdict", "significance", "delta", "evidence", "unassessed_reason"},
                  {"cold_verdict": COLD_VERDICT, "significance": SIGNIFICANCE, "delta": DELTA},
                  ["cold_verdict", "delta"], []),
    "ideation_pool": ({"snapshot", "candidates_total", "prefetched", "gated", "refined",
                       "judge_rejects", "picked_seed_id", "ceiling_verdict", "evidence", "unassessed_reason"},
                      {"snapshot": SNAPSHOT, "ceiling_verdict": CEILING}, ["ceiling_verdict"],
                      ["candidates_total", "prefetched", "gated", "refined", "judge_rejects"]),
}
SECTION_REQUIRED = {"run_facts": ["final_status"], "claim_arc": ["end_to_end_verdict"],
                    "ambition": ["seed_to_contract", "amplifier_arc"], "terminal": ["route", "outcome"],
                    "venue_bar": ["cold_verdict", "delta"], "ideation_pool": ["snapshot", "ceiling_verdict"]}

def die(msg):
    print("ERROR quality-ledger: " + msg); sys.exit(2)

def load(path):
    if not os.path.isfile(path): die("no ledger file at %s (run `init` first)" % path)
    try:
        with open(path) as f: return json.load(f)
    except Exception as e:
        die("ledger is not valid JSON: %s" % e)

def save(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1); f.write("\n")
    os.replace(tmp, path)

def check_record(r, seen_ids):
    rid = r.get("run_id")
    if not isinstance(rid, str) or not rid:
        return "run_id must be a non-empty string (got %r)" % (rid,)
    if rid in seen_ids:
        return "duplicate run_id %s" % rid
    unknown = set(r) - TOP_KEYS
    if unknown:
        return "%s: unknown top-level key(s) %s" % (rid, sorted(unknown))
    for k in REQUIRED_TOP:
        if r.get(k) is None:
            return "%s: missing required field '%s'" % (rid, k)
    if r["recorded_by"] not in RECORDED_BY:
        return "%s: recorded_by %r not in %s" % (rid, r["recorded_by"], RECORDED_BY)
    for name, (allowed, enums, verdicts, counts) in SECTIONS.items():
        sec = r.get(name)
        if not isinstance(sec, dict):
            return "%s: %s must be an object" % (rid, name)
        bad = set(sec) - allowed
        if bad:
            return "%s: %s has unknown key(s) %s" % (rid, name, sorted(bad))
        for k in SECTION_REQUIRED[name]:
            if k not in sec:
                return "%s: %s missing required '%s'" % (rid, name, k)
        for field, enum in enums.items():
            if field in sec and sec[field] not in enum:
                return "%s: %s.%s %r not in closed set" % (rid, name, field, sec[field])
        for field in counts:
            v = sec.get(field)
            if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0):
                return "%s: %s.%s must be a non-negative int or null" % (rid, name, field)
        # capture hygiene (failure/transient.md): a died_mid_run row without its mechanical cause is a
        # poisoning vector — trend findings must be cause-homogeneous, so the cause must be on the record.
        if name == "terminal" and sec.get("route") == "died_mid_run" and not sec.get("cause"):
            return "%s: terminal.route=died_mid_run requires 'cause' (env_transient|oom|code|unknown)" % rid
        # grounding rule: real verdict -> evidence; all-unassessed -> unassessed_reason
        if verdicts:
            assessed = [sec.get(f) for f in verdicts if sec.get(f) not in (None, "unassessed")]
            if assessed and not sec.get("evidence"):
                return "%s: %s has a verdict (%s) but no evidence — grounding rule" % (rid, name, assessed[0])
            if not assessed and not sec.get("unassessed_reason"):
                return "%s: %s is all-unassessed but has no unassessed_reason" % (rid, name)
    return None

def validate_doc(doc):
    if doc.get("schema") != SCHEMA: return "schema must be %s" % SCHEMA
    if not isinstance(doc.get("runs"), list): return "runs must be a list"
    seen = set()
    for r in doc["runs"]:
        err = check_record(r, seen)
        if err: return err
        seen.add(r["run_id"])
    return None

def cmd_init(path):
    if os.path.exists(path): die("refusing to overwrite existing %s" % path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    save(path, {"schema": SCHEMA, "runs": []})
    print("OK quality-ledger: initialized empty ledger at %s" % path)

def cmd_list(path):
    doc = load(path)
    err = validate_doc(doc)
    if err: die(err)
    for r in doc["runs"]:
        print("%-28s %s/%s  claim=%s  amp=%s  venue=%s  pool=%s" % (
            r["run_id"], r["terminal"]["route"], r["terminal"]["outcome"],
            r["claim_arc"]["end_to_end_verdict"], r["ambition"]["amplifier_arc"],
            r["venue_bar"]["delta"], r["ideation_pool"]["ceiling_verdict"]))
    print("OK quality-ledger: %d run(s)" % len(doc["runs"]))

def cmd_validate(path):
    err = validate_doc(load(path))
    if err: die(err)
    print("OK quality-ledger: valid")

TREND_FIELDS = [  # (label, section, field) — fixed order, deterministic output
    ("end_to_end", "claim_arc", "end_to_end_verdict"),
    ("amplifier_arc", "ambition", "amplifier_arc"),
    ("terminal_route", "terminal", "route"),
    ("venue_delta", "venue_bar", "delta"),
    ("significance", "venue_bar", "significance"),
    ("pool_ceiling", "ideation_pool", "ceiling_verdict"),
]

def cmd_trend(path):
    doc = load(path)
    err = validate_doc(doc)
    if err: die(err)
    runs = doc["runs"]  # append order = oldest -> newest
    for label, section, field in TREND_FIELDS:
        vals = [str(r.get(section, {}).get(field)) for r in runs]
        tally = {}
        for v in vals: tally[v] = tally.get(v, 0) + 1
        counts = " ".join("%s=%d" % (v, tally[v]) for v in sorted(tally, key=lambda x: (-tally[x], x)))
        print("TREND %s: %s" % (label, counts or "(empty)"))
        print("ARC %s (oldest->newest): %s" % (label, ",".join(vals) or "(empty)"))
    print("OK quality-ledger: trend over %d run(s)" % len(runs))

def merge_sections(existing, patch_run):
    """Section-level replace-merge: each provided top-level key replaces the existing one wholesale."""
    out = dict(existing)
    for k, v in patch_run.items():
        if k == "run_id": continue
        out[k] = v
    return out

def cmd_apply(path, patch_path):
    doc = load(path)
    err = validate_doc(doc)
    if err: die("ledger invalid before apply: %s" % err)
    try:
        with open(patch_path) as f: patch = json.load(f)
    except Exception as e:
        die("patch is not valid JSON: %s" % e)
    ops = patch.get("ops")
    if not isinstance(ops, list) or not ops: die("patch needs a non-empty ops[] list")
    by_id = {r["run_id"]: i for i, r in enumerate(doc["runs"])}
    applied = []
    for i, op in enumerate(ops):
        kind = op.get("op")
        if kind == "record":
            run = op.get("run") or {}
            rid = run.get("run_id")
            if not rid: die("ops[%d] record: run.run_id required" % i)
            if rid in by_id:
                mode = op.get("if_exists", "refuse")
                if mode == "amend":
                    doc["runs"][by_id[rid]] = merge_sections(doc["runs"][by_id[rid]], run)
                    applied.append("amend %s (record if_exists)" % rid)
                else:
                    die("ops[%d] record: run_id %s already recorded (use if_exists:'amend')" % (i, rid))
            else:
                err = check_record(run, set(by_id))
                if err: die("ops[%d] record: %s" % (i, err))
                doc["runs"].append(run); by_id[rid] = len(doc["runs"]) - 1
                applied.append("record %s" % rid)
        elif kind == "amend":
            rid = op.get("run_id")
            if rid not in by_id: die("ops[%d] amend: unknown run_id %r" % (i, rid))
            run = op.get("run")
            if not isinstance(run, dict) or not run: die("ops[%d] amend: needs a non-empty run object" % i)
            doc["runs"][by_id[rid]] = merge_sections(doc["runs"][by_id[rid]], run)
            applied.append("amend %s" % rid)
        else:
            die("ops[%d]: unknown op %r (record|amend)" % (i, kind))
    err = validate_doc(doc)
    if err: die("ledger would be invalid after apply — refused: %s" % err)
    save(path, doc)
    for a in applied: print("OK quality-ledger: " + a)
    print("OK quality-ledger: applied %d op(s); %d run(s)" % (len(applied), len(doc["runs"])))

def main():
    if len(sys.argv) < 3: die("usage: learn_quality_ledger.py <file> init|list|validate|trend|apply <patch.json>")
    path, cmd = sys.argv[1], sys.argv[2]
    if cmd == "init":       cmd_init(path)
    elif cmd == "list":     cmd_list(path)
    elif cmd == "validate": cmd_validate(path)
    elif cmd == "trend":    cmd_trend(path)
    elif cmd == "apply":
        if len(sys.argv) < 4: die("apply needs <patch.json>")
        cmd_apply(path, sys.argv[3])
    else: die("unknown subcommand %r" % cmd)

if __name__ == "__main__":
    main()
