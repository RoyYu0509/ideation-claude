#!/usr/bin/env bash
# T30 — audited-values registry (REWRITE-CONSOLIDATION-PLAN P1, 2026-06-18). The forward-carried
# `auto-research/audited-values@1` registry is written INCREMENTALLY by `exp_ledger.py register` at
# production time (B2 bless / B1 finalize) so a downstream provenance auditor (/rewrite) can LOOK UP a
# paper number's provenance instead of re-deriving from scratch. This test exercises the CORE subcommand:
#   1. --require-audit on an audit_status=="pass" record registers its extracted_numbers (None-value skipped);
#   2. idempotent — re-registering the same record adds nothing (dedup by ledger_id+quantity+value);
#   3. --require-audit on a "pending" record is fail-closed (registers nothing, reports skipped_reason);
#   4. WITHOUT --require-audit (B1 self-review) a "pending" record IS registered, phase-tagged;
#   5. each entry carries the re-derive provenance (ledger_path, results_file/field, commit_sha, phase).
# Run: bash tests/t30_audited_values_register.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/plugins/paper-polish-ar/scripts/exp_ledger.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok() { echo "PASS  $1"; pass=$((pass+1)); }
no() { echo "FAIL  $1"; fail=$((fail+1)); }

LED="$TMP/run-ledger.json"; REG="$TMP/AUDITED-VALUES.json"

# a ledger with one audited (pass) record carrying a real + a failed extraction, and one pending record.
python3 - "$LED" <<'PY'
import json, sys
led = {"schema": "paper-polish/run-ledger@1", "project_dir": "/ws", "experiment_repo": "/ws/code", "runs": [
  {"ledger_id": "r1", "command": "python run.py", "audit_status": "pass",
   "commit_sha": "abc123", "stdout_sha256": "deadbeef",
   "products": [{"role": "results", "path": "/ws/code/out.json", "rel": "out.json"}],
   "extracted_numbers": [{"token": "acc", "value": "93.8", "source": "results[3].accuracy", "as_written": "93.8"},
                         {"token": "bad", "value": None, "source": "x.y", "error": "KeyError"}]},
  {"ledger_id": "r2", "command": "python run2.py", "audit_status": "pending",
   "products": [{"role": "results", "path": "/ws/code/o2.json", "rel": "o2.json"}],
   "extracted_numbers": [{"token": "f1", "value": "0.71", "source": "f1", "as_written": "0.71"}]}]}
open(sys.argv[1], "w").write(json.dumps(led, indent=2))
PY

# helper: jq-free field reads via python
n_added() { python3 -c "import json,sys;print(json.load(sys.stdin).get('registered'))"; }
reg_count() { python3 -c "import json;print(len(json.load(open('$REG')).get('values',[])))"; }
reg_get()  { python3 -c "import json,sys;vs=json.load(open('$REG'))['values'];print(next((v.get('$2') for v in vs if v.get('ledger_id')=='$1'),'<none>'))"; }

# 1. require-audit on a pass record → 1 registered (None-value extraction skipped)
a="$(python3 "$CLI" register --ledger "$LED" --ledger-id r1 --registry "$REG" --phase B2 --require-audit | n_added)"
[ "$a" = "1" ] && ok "pass-record registers its valued extraction (None skipped)" || no "expected 1 registered, got $a"

# 2. idempotent re-register → 0 added, count stays 1
a="$(python3 "$CLI" register --ledger "$LED" --ledger-id r1 --registry "$REG" --phase B2 --require-audit | n_added)"
[ "$a" = "0" ] && [ "$(reg_count)" = "1" ] && ok "idempotent re-register adds nothing" || no "re-register not idempotent (added=$a, count=$(reg_count))"

# 3. require-audit on a pending record → fail-closed, 0 added
a="$(python3 "$CLI" register --ledger "$LED" --ledger-id r2 --registry "$REG" --phase B2 --require-audit | n_added)"
[ "$a" = "0" ] && [ "$(reg_count)" = "1" ] && ok "fail-closed: pending record not registered under --require-audit" || no "pending leaked (added=$a, count=$(reg_count))"

# 4. B1 path (no --require-audit) registers the pending record, phase-tagged
a="$(python3 "$CLI" register --ledger "$LED" --ledger-id r2 --registry "$REG" --phase B1 | n_added)"
[ "$a" = "1" ] && [ "$(reg_count)" = "2" ] && ok "B1 self-review record registers without --require-audit" || no "B1 register failed (added=$a, count=$(reg_count))"

# 5. provenance fields carried for re-derivation
[ "$(reg_get r1 value)" = "93.8" ]                  && ok "entry value"            || no "value wrong: $(reg_get r1 value)"
[ "$(reg_get r1 quantity)" = "results[3].accuracy" ] && ok "entry quantity (field path)" || no "quantity wrong: $(reg_get r1 quantity)"
[ "$(reg_get r1 commit_sha)" = "abc123" ]            && ok "entry commit_sha"        || no "commit_sha wrong: $(reg_get r1 commit_sha)"
[ "$(reg_get r1 results_file)" = "/ws/code/out.json" ] && ok "entry results_file"    || no "results_file wrong: $(reg_get r1 results_file)"
[ "$(reg_get r1 phase)" = "B2" ]                     && ok "entry phase tag (B2)"    || no "phase wrong: $(reg_get r1 phase)"
[ "$(reg_get r2 phase)" = "B1" ]                     && ok "entry phase tag (B1)"    || no "phase wrong: $(reg_get r2 phase)"
[ "$(reg_get r2 audit_status)" = "pending" ]        && ok "B1 entry keeps self-review audit_status" || no "audit_status wrong: $(reg_get r2 audit_status)"

# 6. P-7 fix (dossier 02, 2026-07-07): a LATER B2-audit re-registration of the SAME (ledger_id,quantity,value)
#    upgrades the existing row's audit_status/phase IN PLACE — never silently dropped, never a duplicate row.
python3 -c "
import json
led = json.load(open('$LED'))
for r in led['runs']:
    if r['ledger_id'] == 'r2': r['audit_status'] = 'pass'   # simulate: r2's own ledger record got B2-audited
json.dump(led, open('$LED', 'w'), indent=2)
"
out="$(python3 "$CLI" register --ledger "$LED" --ledger-id r2 --registry "$REG" --phase B2 --require-audit)"
a="$(echo "$out" | python3 -c "import json,sys;print(json.load(sys.stdin).get('registered'))")"
u="$(echo "$out" | python3 -c "import json,sys;print(json.load(sys.stdin).get('upgraded'))")"
[ "$a" = "0" ] && [ "$u" = "1" ] && [ "$(reg_count)" = "2" ] && [ "$(reg_get r2 audit_status)" = "pass" ] && [ "$(reg_get r2 phase)" = "B2" ] \
  && ok "B2-audit upgrade of an already-registered value updates audit_status/phase in place (no duplicate row)" \
  || no "upgrade failed (added=$a, upgraded=$u, count=$(reg_count), audit_status=$(reg_get r2 audit_status), phase=$(reg_get r2 phase))"

# schema stamp
[ "$(python3 -c "import json;print(json.load(open('$REG'))['schema'])")" = "auto-research/audited-values@1" ] \
  && ok "registry schema stamp" || no "registry schema wrong"

# ── review is DIAGNOSE-ONLY since 39874f9 (registerAudited forward-carry retired to /rewrite), and since
#    2026-07-05 review.js itself is RETIRED for the REVIEW-OWNER protocol. Assert the retired blessed-swap
#    path stays gone from the whole new review chain (protocol + leaves).
grep -qE 'exp_ledger\.py" bless|blessRecord\(' \
    "$ROOT/plugins/paper-polish-ar/spec/review-protocol.md" "$ROOT"/plugins/paper-polish-ar/spec/review/*.md \
  && no "review chain: retired blessed-swap (bless) still present" \
  || ok "review chain: blessed-swap (bless) retired — register is the only forward-carry"

echo "----"
echo "T30: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
