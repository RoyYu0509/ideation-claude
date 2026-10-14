#!/usr/bin/env bash
# concern_prose_lint.sh — TASK_STATUS.md "## Editorial direction" staleness lint.
#
# WHY: TASK_STATUS.concerns.json (the structured ledger) and TASK_STATUS.md's hand-authored "## Editorial
# direction (top strengthening needs)" prose are two mirrors of the same facts. The structured ledger stays
# correct (gateHandoffApproval reads it as pure JSON fields); the prose is written once and NEVER mechanically
# re-checked against later ledger changes. Real incident (gate-invariant-relaxed-speculative-decoding,
# 2026-07-16): K1's structured status moved to "descoped_infeasible_at_scale" while the SAME file's Editorial
# direction section still read "K1 is the whole paper" — a direct, uncaught contradiction. This is advisory
# (D12 precedent: a consistency lint is a reviewer aid, never a silent auto-edit, never a hard block) — it
# flags; spec/research.js decides whether/when a repeated flag escalates to a required disposition.
#
# Usage:  bin/concern_prose_lint.sh <workspace>
# Stdout: ONE line — a compact JSON object:
#   { "checked": <int>, "section_found": bool,
#     "stale": [ { "id", "status", "item_excerpt", "line" }, ... ],
#     "section_sha256": "<hash of the Editorial-direction section text, or null>",
#     "note": "<only present on a defensive skip>" }
# Exit: ALWAYS 0 — advisory-only, never blocks a caller.
set -euo pipefail

WS="${1:-}"
[ -z "$WS" ] && { echo '{"checked":0,"section_found":false,"stale":[],"section_sha256":null,"note":"usage: concern_prose_lint.sh <workspace>"}'; exit 0; }

python3 - "$WS" <<'PY'
import json, re, sys, hashlib, os

ws = sys.argv[1]
concerns_path = os.path.join(ws, "TASK_STATUS.concerns.json")
status_path   = os.path.join(ws, "TASK_STATUS.md")

def out(payload):
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)  # ALWAYS 0 — advisory-only, mirrors verdict_fidelity's do-no-harm posture

if not os.path.isfile(concerns_path) or not os.path.isfile(status_path):
    out({"checked": 0, "section_found": False, "stale": [], "section_sha256": None,
         "note": "TASK_STATUS.concerns.json or TASK_STATUS.md absent — nothing to check"})

try:
    rows = (json.load(open(concerns_path, encoding="utf-8")) or {}).get("open_concerns") or []
except Exception as e:
    out({"checked": 0, "section_found": False, "stale": [], "section_sha256": None,
         "note": f"TASK_STATUS.concerns.json unreadable ({e}) — skipped"})

text_lines = open(status_path, encoding="utf-8", errors="replace").read().splitlines()

# ---- locate the "## Editorial direction" section (tolerant heading match; SKILL.md pins the literal string,
#      but older/pre-pin runs may not have it byte-exact) ----
HEAD_RE = re.compile(r'^##\s+Editorial\s+direction\b', re.I)
start = next((i for i, l in enumerate(text_lines) if HEAD_RE.match(l)), None)
if start is None:
    out({"checked": len(rows), "section_found": False, "stale": [], "section_sha256": None,
         "note": "no '## Editorial direction' heading found in TASK_STATUS.md"})

end = next((j for j in range(start + 1, len(text_lines)) if text_lines[j].startswith("## ")), len(text_lines))
section_lines = text_lines[start + 1:end]
section_text = "\n".join(section_lines)
section_sha  = hashlib.sha256(section_text.encode("utf-8")).hexdigest()

# ---- split into list items (numbered "1." or bulleted "-"/"*"); whole section = one item if no list ----
ITEM_RE = re.compile(r'^\s*(?:\d+[.)]|[-*])\s+')
item_starts = [i for i, l in enumerate(section_lines) if ITEM_RE.match(l)]
if not item_starts:
    items = [(start + 1, section_text)]
else:
    bounds = item_starts + [len(section_lines)]
    items = [(start + 1 + bounds[k], "\n".join(section_lines[bounds[k]:bounds[k + 1]]))
             for k in range(len(item_starts))]

ACK_TOKENS = ["descoped", "closed", "resolved", "no longer", "superseded", "moot",
              "n/a", "deferred", "killed", "out of scope", "future work",
              "removed from scope", "not part of"]

stale = []
for row in rows:
    rid = (row or {}).get("id")
    status = (row or {}).get("status")
    if not rid or not status:
        continue                                    # defensive: an unparseable row contributes nothing
    if status in ("open", "reopened"):
        continue                                     # still live -> low false-positive risk, never flag
    id_re = re.compile(r'\b' + re.escape(str(rid)) + r'\b')
    status_tokens = [t for t in re.split(r'[_\-\s]+', str(status).lower()) if len(t) >= 5]
    ack_words = ACK_TOKENS + [str(status).replace("_", " ").replace("-", " ").lower()] + status_tokens
    for line_no, item_text in items:
        if not id_re.search(item_text):
            continue
        low = item_text.lower()
        if any(tok in low for tok in ack_words):
            continue                                 # SELF-CONSISTENCY ESCAPE HATCH: prose already says so
        stale.append({"id": rid, "status": status,
                       "item_excerpt": item_text.strip()[:200], "line": line_no})
        break                                         # one flag per id is enough

out({"checked": len(rows), "section_found": True, "stale": stale, "section_sha256": section_sha})
PY
