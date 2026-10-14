#!/usr/bin/env bash
# bin/validate_envelope.sh — RC-3: validate an L1 return envelope against spec/l1-envelope-schema.json.
# SELF-CONTAINED — interprets a pragmatic subset of JSON Schema (type / required / enum / properties /
# items) in pure python, with NO jsonschema dependency (must never pip-install mid-run: fact #7 background
# subagents auto-deny prompts). The schema file stays a real JSON Schema so it transfers verbatim to a
# future Workflow agent({schema}) call.
#
# Usage: bin/validate_envelope.sh <envelope.json>   -> exit 0 valid, exit 2 invalid (+ reasons)
set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SCHEMA="${ENVELOPE_SCHEMA:-$ROOT/spec/l1-envelope-schema.json}"
ENVF="${1:-}"
[ -n "$ENVF" ]    || { echo "ERROR validate_envelope: need <envelope.json>"; exit 2; }
[ -f "$ENVF" ]    || { echo "ERROR validate_envelope: envelope not found: $ENVF"; exit 2; }
[ -f "$SCHEMA" ]  || { echo "ERROR validate_envelope: schema not found: $SCHEMA"; exit 2; }

SCHEMA="$SCHEMA" ENVF="$ENVF" python3 - <<'PY'
import os, sys, json
def fail(m): print("ERROR validate_envelope: " + m); sys.exit(2)
try:    schema = json.load(open(os.environ["SCHEMA"]))
except Exception as e: fail("bad schema file (%s)" % e)
try:    data   = json.load(open(os.environ["ENVF"]))
except Exception as e: fail("envelope is not valid JSON (%s)" % e)

JTYPES = {"object": dict, "array": list, "string": str, "number": (int, float),
          "integer": int, "boolean": bool, "null": type(None)}
errs = []
def check(node, sch, path):
    t = sch.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        if not any(x in JTYPES and isinstance(node, JTYPES[x]) for x in types):
            errs.append("%s: expected type %s, got %s" % (path, t, type(node).__name__)); return
    if "enum" in sch and node not in sch["enum"]:
        errs.append("%s: %r not in enum %r" % (path, node, sch["enum"]))
    if isinstance(node, dict):
        for r in sch.get("required", []):
            if r not in node: errs.append("%s: missing required '%s'" % (path, r))
        for k, subs in (sch.get("properties") or {}).items():
            if k in node: check(node[k], subs, path + "." + k)
    if isinstance(node, list) and "items" in sch:
        for i, el in enumerate(node): check(el, sch["items"], "%s[%d]" % (path, i))

check(data, schema, "envelope")
if errs:
    fail("envelope does not satisfy l1-envelope-schema.json:\n  - " + "\n  - ".join(errs))
print("OK validate_envelope: envelope satisfies the schema")
PY
