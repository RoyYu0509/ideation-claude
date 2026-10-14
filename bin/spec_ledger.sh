#!/usr/bin/env bash
# bin/spec_ledger.sh — append/UPSERT one row of the SPEC EVOLUTION ledger.
#
# WHY THIS EXISTS. The loop's product is a RESEARCH SPECIFICATION: every round executes the current
# spec, evaluates the result, and RE-AUTHORS the spec (generateHandoff). "How the spec evolved" is
# therefore the run's primary record — and it must not depend on an L0 reproduction remembering to
# compose JSON by hand (the [[MECH]] accounting-in-code rule: a ledger an LLM hand-writes is a ledger
# that silently stops being written). This script derives EVERY field mechanically from artifacts that
# already exist on disk; it reasons about nothing.
#
# Usage:  bin/spec_ledger.sh <workspace> <round>
#   Reads : <ws>/SPEC/SPEC-v<round>.md          (the snapshot generateHandoff just copied)
#           <ws>/HANDOFF.ambition.target.json   (the RAISED target, when the amplifier earned one)
#           <ws>/HANDOFF.ambition.locked.json   (the Phase-0(C) floor)
#           <ws>/HANDOFF.scale-contract.locked.json
#           <ws>/TASK_STATUS.concerns.json
#   Writes: <ws>/SPEC/spec-ledger.json          ({schema, rows:[...]}), UPSERTed by round
#   Prints: "OK spec-ledger round <n> (<rows> rows)" | "ERROR ..." on stderr
# Exit:   0 ok · 2 bad args / missing snapshot.
#
# TOLERANT BY DESIGN: every input except the snapshot is optional — an absent file yields nulls, never
# a crash. A round re-authored twice (rescue loopback, amplifier re-entry) REPLACES its own row rather
# than appending a duplicate, so the ledger stays one row per round.
set -uo pipefail

WS="${1:-}"; ROUND="${2:-}"
[ -n "$WS" ] && [ -n "$ROUND" ] || { echo "ERROR spec_ledger: need <workspace> <round>" >&2; exit 2; }
[ -d "$WS" ] || { echo "ERROR spec_ledger: workspace not found: $WS" >&2; exit 2; }

WS="$WS" ROUND="$ROUND" TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)" python3 - <<'PY'
import os, sys, json, hashlib

ws    = os.environ["WS"]
rnd   = int(os.environ["ROUND"])
ts    = os.environ["TS"]
specd = os.path.join(ws, "SPEC")
snap  = os.path.join(specd, f"SPEC-v{rnd}.md")

if not os.path.isfile(snap):
    sys.stderr.write(f"ERROR spec_ledger: missing snapshot {snap}\n"); sys.exit(2)

def jload(rel):
    try:
        with open(os.path.join(ws, rel), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()

# ── ambition: the CURRENT target (raised) if present, else the Phase-0(C) locked floor ────────────
target = jload("HANDOFF.ambition.target.json")
floor  = jload("HANDOFF.ambition.locked.json")
amb    = target or floor
amb_src = "target" if target else ("locked" if floor else "none")

def g(d, *path):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d

def n_of(v):
    return len(v) if isinstance(v, (list, dict)) else None

ambition = {
    "source":         amb_src,
    "central_result": g(amb, "central_result") or g(amb, "content", "central_result"),
    "title_promise":  g(amb, "title_promise")  or g(amb, "content", "title_promise"),
    "scope_n":        n_of(g(amb, "scope")        or g(amb, "content", "scope")),
    "named_rivals_n": n_of(g(amb, "named_rivals") or g(amb, "content", "named_rivals")),
    # a target.json existing at all IS the raise signal (raiseAmbitionTarget only writes it on an earned raise)
    "raised_above_floor": bool(target),
}

# ── scale contract: how many criteria the spec binds itself to ────────────────────────────────────
sc  = jload("HANDOFF.scale-contract.locked.json")
crit = g(sc, "criteria") or g(sc, "content", "criteria")
scale = {"criteria_n": n_of(crit),
         "criteria_ids": sorted(crit.keys()) if isinstance(crit, dict) else None}

# ── open concerns: the rigor debt the spec still carries into the next round ──────────────────────
led  = jload("TASK_STATUS.concerns.json") or {}
rows = led.get("open_concerns") if isinstance(led.get("open_concerns"), list) else []
def is_open(r):
    return isinstance(r, dict) and r.get("status") in ("open", "reopened") and r.get("closed_round") is None
open_rows  = [r for r in rows if is_open(r)]
major_rows = [r for r in open_rows if r.get("severity") == "major"]
concerns = {
    "open_n":       len(open_rows),
    "open_major_n": len(major_rows),
    "open_major_ids": sorted(str(r.get("id")) for r in major_rows if r.get("id")),
}

row = {"round": rnd, "ts": ts,
       "spec_file": f"SPEC/SPEC-v{rnd}.md", "spec_sha256": sha256(snap),
       "ambition": ambition, "scale": scale, "concerns": concerns}

# ── UPSERT by round, keep rows sorted ─────────────────────────────────────────────────────────────
path = os.path.join(specd, "spec-ledger.json")
try:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc, dict) or not isinstance(doc.get("rows"), list):
        raise ValueError
except Exception:
    doc = {"schema": "auto-research-spec-ledger@1", "rows": []}

prev = next((r for r in doc["rows"] if r.get("round") == rnd - 1), None)
row["changed_since_prev"] = (prev.get("spec_sha256") != row["spec_sha256"]) if prev else None

doc["rows"] = [r for r in doc["rows"] if r.get("round") != rnd] + [row]
doc["rows"].sort(key=lambda r: r.get("round", 0))
os.makedirs(specd, exist_ok=True)
with open(path, "w", encoding="utf-8") as f:
    json.dump(doc, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"OK spec-ledger round {rnd} ({len(doc['rows'])} rows)")
PY
