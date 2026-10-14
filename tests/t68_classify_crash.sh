#!/usr/bin/env bash
# T68 — bin/classify_crash.py: the mechanical crash-cause classifier (capture hygiene, ARIS item 4).
# Cause closed-set env_transient|oom|code|unknown; OOM never signature-classified as transient; scan is a
# detector (always exit 0). Regex twin of plugins/experiment-lab-ar/spec/failure/transient.md.
# Run: bash tests/t68_classify_crash.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CC="$ROOT/bin/classify_crash.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

cause_of(){ python3 "$CC" classify --exit-code "$1" --tail-file "$2" 2>/dev/null | awk '/^CAUSE/{print $2}'; }

# 1) classify — each signature family lands in its cause; OOM is NOT env_transient
printf 'anthropic API error 429: rate limit exceeded\n' > "$TMP/t429"
[ "$(cause_of 1 "$TMP/t429")" = env_transient ] && ok "429/rate-limit tail => env_transient" || no "429 misclassified"
printf 'no output\n' > "$TMP/tkill"
[ "$(cause_of 'killed (PID died mid-run, no exitcode)' "$TMP/tkill")" = env_transient ] \
  && ok "PID-dead-no-exitcode => env_transient" || no "pid-dead misclassified"
printf 'requests.exceptions.ConnectionError: connection refused\n' > "$TMP/tnet"
[ "$(cause_of 1 "$TMP/tnet")" = env_transient ] && ok "connection refused => env_transient" || no "network misclassified"
printf 'torch.cuda.OutOfMemoryError: CUDA out of memory. Tried to allocate 20 GiB\n' > "$TMP/toom"
C_OOM="$(cause_of 1 "$TMP/toom")"
[ "$C_OOM" = oom ] && ok "CUDA OOM => oom (awaiting adjudication)" || no "OOM misclassified ($C_OOM)"
[ "$C_OOM" != env_transient ] && ok "OOM is NEVER signature-classified env_transient" || no "OOM leaked into env_transient"
printf 'Traceback (most recent call last):\n  File "run.py", line 3\nAssertionError: bad\n' > "$TMP/tcode"
[ "$(cause_of 1 "$TMP/tcode")" = code ] && ok "traceback => code" || no "traceback misclassified"
printf 'zsh: something odd happened\n' > "$TMP/tunk"
[ "$(cause_of 7 "$TMP/tunk")" = unknown ] && ok "no signature => unknown" || no "garbage not unknown"

# 2) annotate — adds cause per crash into the marker (idempotent), prints CAUSES
python3 - "$TMP/.crash-EXPERIMENTS_DONE.json" <<'PY'
import json,sys
json.dump({"schema":"auto-research-crash@1","paper":"p","milestone":"EXPERIMENTS_DONE","loop_round":1,"at":"t",
 "crashes":[{"phase":"B1","ledger_id":"e1","exit_code":"killed (PID died mid-run, no exitcode)","stdout_tail":"","stdout_log":""},
            {"phase":"B1","ledger_id":"e2","exit_code":"1","stdout_tail":"CUDA out of memory","stdout_log":""}]},
 open(sys.argv[1],"w"))
PY
OUT="$(python3 "$CC" annotate --marker "$TMP/.crash-EXPERIMENTS_DONE.json")"
echo "$OUT" | grep -q "CAUSES env_transient,oom" && ok "annotate prints the unique cause list" || no "annotate CAUSES wrong: $OUT"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['crashes'][0]['cause']=='env_transient' and d['crashes'][1]['cause']=='oom'" \
  "$TMP/.crash-EXPERIMENTS_DONE.json" && ok "annotate wrote cause fields into the marker" || no "marker not annotated"

# 3) scan — crash markers + FAILURES lines (tagged, legacy-untagged, RESOLVED pairing); always exit 0
WS="$TMP/ws"; mkdir -p "$WS"; cp "$TMP/.crash-EXPERIMENTS_DONE.json" "$WS/"
cat > "$WS/FAILURES.md" <<'EOF'
[t1] EXPERIMENTS_DONE: detached run crashed (exit!=0) — e1; see marker. [cause:env_transient]
[t2] RESULTS_ON_DISK: detached run crashed (exit!=0) — old vintage line with connection reset by peer.
[t3] EXPERIMENTS_DONE: RESOLVED — prior crash cleared, milestone completed on re-run.
EOF
python3 "$CC" scan --ws "$WS" --out "$WS/transient-events.json" >/dev/null 2>&1; rc=$?
[ $rc -eq 0 ] && [ -f "$WS/transient-events.json" ] && ok "scan exits 0 and writes the ledger" || no "scan failed (rc=$rc)"
python3 - "$WS/transient-events.json" <<'PY' && ok "scan: causes + RESOLVED pairing + legacy re-classification correct" || no "scan ledger content wrong"
import json,sys
d=json.load(open(sys.argv[1])); ev=d["events"]
fl={e.get("milestone"):e for e in ev if e["source"]=="failures_line"}
assert fl["EXPERIMENTS_DONE"]["cause"]=="env_transient" and fl["EXPERIMENTS_DONE"]["resolved"] is True
assert fl["RESULTS_ON_DISK"]["cause"]=="env_transient" and fl["RESULTS_ON_DISK"]["resolved"] is False
mk=[e for e in ev if e["source"]=="crash_marker"]
assert {e["cause"] for e in mk}=={"env_transient","oom"}, mk
PY
python3 "$CC" scan --ws "$TMP/nonexistent-ws" >/dev/null 2>&1 \
  && ok "scan on a missing workspace degrades to exit 0 (detector discipline)" || no "scan not fail-open"

echo "----"; echo "t68_classify_crash: $pass passed, $fail failed"; [ "$fail" = 0 ]
