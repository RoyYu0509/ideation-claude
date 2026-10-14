#!/usr/bin/env bash
# bin/lock_contracts.sh — DETERMINISTIC Phase-0(C) lock of the two machine-readable contracts.
#
# WHY. The whole anti-under-scale / anti-reward-hack apparatus (V5 ratchet, V8 scale audit, the §4c
# ambition reconciliation) rests on an IMMUTABLE baseline snapshot of §4b/§4c taken at Phase 0(C). The
# spec said "LOCK §4b -> HANDOFF.scale-contract.locked.json" but left the WRITE to the LLM, which skipped
# it — so the locks never existed, V5 silently treated the absence as "legacy run", and a post-Phase-0
# WEAKEN (the K3 1.654 -> relative change) became invisible. This makes the lock a real, checkable file.
#
# It captures the §4b SCALE-CONTRACT and §4c AMBITION-CONTRACT fenced blocks from <ws>/HANDOFF.md VERBATIM
# (raw text + sha256 + provenance), so V5 can diff "did the contract change since lock?" and the verifier
# can read the contracted anchors. Dependency-free (no pyyaml): the lock stores the block text, not a parse.
#
# Usage: bin/lock_contracts.sh <workspace> [--ratchet]
#   default  — FIRST lock: write both .locked.json; REFUSE (exit 2) if either already exists (a re-lock
#              without --ratchet would silently overwrite the immutable baseline).
#   --ratchet — explicit re-lock (an audited TIGHTEN/REDIRECT/RAISE per §4b/§4c ratchet); overwrites,
#              recording prev_sha256 so the change is traceable.
#   exit 0 = locked, exit 2 = error (missing HANDOFF / missing §4b or §4c block / illegal overwrite).
set -euo pipefail

WS="${1:-}"; MODE="${2:-}"
[ -n "$WS" ] || { echo "ERROR lock_contracts: need <workspace>"; exit 2; }
HANDOFF="$WS/HANDOFF.md"
[ -f "$HANDOFF" ] || { echo "ERROR lock_contracts: no HANDOFF.md at $HANDOFF"; exit 2; }
RATCHET=0; [ "$MODE" = "--ratchet" ] && RATCHET=1

CODE_COMMIT="$(git -C "$WS/code" rev-parse HEAD 2>/dev/null || echo '')"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

WS="$WS" HANDOFF="$HANDOFF" RATCHET="$RATCHET" CODE_COMMIT="$CODE_COMMIT" NOW="$NOW" python3 - <<'PY'
import os, sys, json, hashlib

ws = os.environ["WS"]; handoff = os.environ["HANDOFF"]
ratchet = os.environ["RATCHET"] == "1"
code_commit = os.environ["CODE_COMMIT"]; now = os.environ["NOW"]
lines = open(handoff, encoding="utf-8").read().splitlines()

def extract(phrase):
    """Find a markdown header line containing <phrase>, then capture the first fenced ``` block after it."""
    hdr = None
    for i, ln in enumerate(lines):
        s = ln.lstrip()
        if s.startswith("#") and phrase in ln:
            hdr = i; break
    if hdr is None:
        return None, "header containing %r not found" % phrase
    # find the opening fence after the header
    op = None
    for i in range(hdr + 1, len(lines)):
        if lines[i].lstrip().startswith("```"):
            op = i; break
        # stop if we hit the NEXT header before any fence (block is missing)
        if lines[i].lstrip().startswith("#") and i > hdr:
            return None, "no fenced block between %r header and the next header" % phrase
    if op is None:
        return None, "no opening fence after %r header" % phrase
    cl = None
    for i in range(op + 1, len(lines)):
        if lines[i].lstrip().startswith("```"):
            cl = i; break
    if cl is None:
        return None, "unterminated fenced block after %r header" % phrase
    body = "\n".join(lines[op + 1:cl]).strip("\n")
    if not body.strip():
        return None, "fenced block after %r header is empty" % phrase
    return body, None

targets = [
    ("SCALE-CONTRACT",   "HANDOFF.scale-contract.locked.json", "auto-research-scale-contract-lock@1", "HANDOFF.md §4b SCALE-CONTRACT"),
    ("AMBITION CONTRACT","HANDOFF.ambition.locked.json",       "auto-research-ambition-contract-lock@1","HANDOFF.md §4c AMBITION CONTRACT"),
]

# Validate BOTH blocks exist before writing EITHER (atomic-ish: never a half lock).
blocks = {}
for phrase, fname, schema, source in targets:
    body, err = extract(phrase)
    if err:
        print("ERROR lock_contracts: %s" % err); sys.exit(2)
    blocks[fname] = (body, schema, source)

for phrase, fname, schema, source in targets:
    out = os.path.join(ws, fname)
    prev_sha = None
    if os.path.exists(out):
        if not ratchet:
            print("ERROR lock_contracts: %s already exists; re-lock requires --ratchet "
                  "(refusing to silently overwrite the immutable baseline)" % fname); sys.exit(2)
        try:
            prev_sha = (json.load(open(out)) or {}).get("sha256")
        except Exception:
            prev_sha = None
    body, schema, source = blocks[fname]
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    rec = {"schema": schema, "source": source, "locked_at": now,
           "locked_code_commit": code_commit or None, "ratchet": ratchet,
           "prev_sha256": prev_sha, "sha256": sha, "content": body}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)
    print("OK lock_contracts: wrote %s (sha256 %s%s)" % (fname, sha[:12], " RATCHET" if ratchet else ""))
PY

# best-effort deterministic event (observability; never blocks). Land it in the DATA root's state/.
DATA_ROOT="$(cd "$WS/../.." 2>/dev/null && pwd || true)"
[ -n "$DATA_ROOT" ] && CLAUDE_PROJECT_DIR="$DATA_ROOT" bash "$(dirname "${BASH_SOURCE[0]}")/log_event.sh" \
  contracts_locked "{\"ws\":\"$WS\",\"ratchet\":$RATCHET}" 2>/dev/null || true
