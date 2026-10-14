#!/usr/bin/env bash
# t10 — bin/validate_envelope.sh validates an L1 envelope against spec/l1-envelope-schema.json (RC-3).
# The envelope is no longer trusted on faith; a malformed return is caught before L0 acts on it. Standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
chk(){ if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

printf '{"status":"done","artifacts":["a.md"],"metrics":{"subagents_spawned":3},"detached":null}' > "$TMP/ok.json"
chk "valid envelope -> exit 0" "bash '$ROOT/bin/validate_envelope.sh' '$TMP/ok.json' >/dev/null 2>&1"

printf '{"status":"finished","artifacts":["a"],"metrics":{}}' > "$TMP/badstatus.json"
chk "status not in enum -> exit 2" "! bash '$ROOT/bin/validate_envelope.sh' '$TMP/badstatus.json' >/dev/null 2>&1"

printf '{"status":"done","artifacts":"a.md","metrics":{}}' > "$TMP/badart.json"
chk "artifacts not an array -> exit 2" "! bash '$ROOT/bin/validate_envelope.sh' '$TMP/badart.json' >/dev/null 2>&1"

printf '{"status":"done","artifacts":[]}' > "$TMP/nometrics.json"
chk "missing required 'metrics' -> exit 2" "! bash '$ROOT/bin/validate_envelope.sh' '$TMP/nometrics.json' >/dev/null 2>&1"

printf '{"status":"long_run_fired","artifacts":[],"metrics":{},"detached":{"pidfile":"p","state_path":"s"}}' > "$TMP/detok.json"
chk "detached object + long_run_fired -> exit 0" "bash '$ROOT/bin/validate_envelope.sh' '$TMP/detok.json' >/dev/null 2>&1"

printf 'not json at all' > "$TMP/notjson.json"
chk "non-JSON envelope -> exit 2" "! bash '$ROOT/bin/validate_envelope.sh' '$TMP/notjson.json' >/dev/null 2>&1"

echo "----"; echo "t10_envelope_schema: $pass passed, $fail failed"; [ "$fail" = 0 ]
