#!/usr/bin/env bash
# probe_run.sh — sandboxed executor for ideation premise/theory probes.
#
#   bash bin/probe_run.sh <probe_dir> [--suffix .replay]
#
# Runs <probe_dir>/probe.py under the plugin venv with cwd=<probe_dir>, a hard
# timeout, and a no-network static gate. Captures stdout to
# <probe_dir>/stdout<suffix>.txt and writes <probe_dir>/meta<suffix>.json
# (sha256 of script+stdout, runtime, exit code, utc, venv requirements sha).
#
# CONTRACT (verification-bundle spec): the probe's LAST stdout line must be a
# machine-readable verdict:
#   PROBE_VERDICT: {"id":"P1-spectrum","pass":false,"value":8.86,"threshold":1.0,"direction":"<="}
# A probe that FAILS its premise still exits 0 here — a refuting probe is a
# SUCCESSFUL probe run. Exit codes: 0 verdict captured; 3 no PROBE_VERDICT
# line; 4 timeout; 5 forbidden import / path guard; other = probe crash code.
#
# Sandbox bounds: CPU-only tiny scripts (<=~200 lines); no network imports
# (mechanical grep below — probes work from extracted formulas, never fetch);
# writes confined to the probe's own dir (cwd); timeout from
# scout.probe_timeout_sec (PROBE_TIMEOUT env overrides, for tests).
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

PROBE_DIR="${1:?usage: probe_run.sh <probe_dir> [--suffix .replay]}"
shift
SUFFIX=""
if [[ "${1:-}" == "--suffix" ]]; then
  SUFFIX="${2:?--suffix needs a value}"
fi

PROBE_DIR="$(cd "$PROBE_DIR" && pwd)"
SCRIPT="$PROBE_DIR/probe.py"
[[ -f "$SCRIPT" ]] || { echo "probe_run: no probe.py in $PROBE_DIR" >&2; exit 2; }

# Path guard: probes live only under an ideations tree (AR_PROBE_DIR_OK=1 for pytest fixtures).
if [[ "${AR_PROBE_DIR_OK:-0}" != "1" && "$PROBE_DIR" != */data/ideations/* ]]; then
  echo "probe_run: refusing probe dir outside */data/ideations/* : $PROBE_DIR" >&2
  exit 5
fi

# No-network static gate (probes derive from committed formulas; they never fetch).
if grep -nE '^[[:space:]]*(import|from)[[:space:]]+(requests|urllib|socket|http|ftplib|smtplib|subprocess)\b' "$SCRIPT" \
   || grep -nE 'os\.(system|popen)' "$SCRIPT"; then
  echo "probe_run: forbidden import/call in probe.py (no network / no subprocess)" >&2
  exit 5
fi

if [[ -n "${PROBE_TIMEOUT:-}" ]]; then
  TIMEOUT_S="$PROBE_TIMEOUT"
else
  TIMEOUT_S="$(bash "$PLUGIN_ROOT/bin/cfgval.sh" scout.probe_timeout_sec)"
fi

# System python3 drives the timeout (portable on darwin — no coreutils `timeout`);
# the probe itself runs under the plugin venv via run_py.sh.
PLUGIN_ROOT="$PLUGIN_ROOT" PROBE_DIR="$PROBE_DIR" SCRIPT="$SCRIPT" SUFFIX="$SUFFIX" TIMEOUT_S="$TIMEOUT_S" \
python3 - <<'PY'
import hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone

plugin_root = os.environ["PLUGIN_ROOT"]
probe_dir = os.environ["PROBE_DIR"]
script = os.environ["SCRIPT"]
suffix = os.environ["SUFFIX"]
timeout_s = float(os.environ["TIMEOUT_S"])

stdout_path = os.path.join(probe_dir, f"stdout{suffix}.txt")
meta_path = os.path.join(probe_dir, f"meta{suffix}.json")

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

t0 = time.monotonic()
timed_out = False
try:
    proc = subprocess.run(
        ["bash", os.path.join(plugin_root, "bin", "run_py.sh"), script],
        cwd=probe_dir, timeout=timeout_s, capture_output=True, text=True,
    )
    exit_code = proc.returncode
    stdout = proc.stdout
    if proc.stderr:
        sys.stderr.write(proc.stderr)
except subprocess.TimeoutExpired as e:
    timed_out = True
    exit_code = -1
    stdout = (e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or ""))
runtime_s = round(time.monotonic() - t0, 3)

with open(stdout_path, "w", encoding="utf-8") as f:
    f.write(stdout)

req_sha = None
req_path = os.path.join(plugin_root, "scripts", "requirements.txt")
if os.path.exists(req_path):
    req_sha = sha256(req_path)

verdict = None
for line in reversed([l for l in stdout.splitlines() if l.strip()]):
    if line.startswith("PROBE_VERDICT:"):
        try:
            verdict = json.loads(line[len("PROBE_VERDICT:"):].strip())
        except json.JSONDecodeError:
            verdict = None
        break

meta = {
    "sha256_script": sha256(script),
    "sha256_stdout": sha256(stdout_path),
    "runtime_s": runtime_s,
    "exit_code": exit_code,
    "timed_out": timed_out,
    "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "requirements_sha256": req_sha,
    "verdict": verdict,
}
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)

if timed_out:
    print(f"probe_run: TIMEOUT after {timeout_s}s", file=sys.stderr)
    sys.exit(4)
if exit_code != 0:
    print(f"probe_run: probe crashed (exit {exit_code}) — see stderr above", file=sys.stderr)
    sys.exit(exit_code if 0 < exit_code < 128 else 1)
if verdict is None:
    print("probe_run: probe exited 0 but printed no parseable PROBE_VERDICT line", file=sys.stderr)
    sys.exit(3)
print(json.dumps({"verdict": verdict, "stdout": stdout_path, "meta": meta_path}))
PY
