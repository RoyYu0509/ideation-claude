#!/usr/bin/env bash
# T41 (contract) — the experiment detach pidfile must be a BAKED ABSOLUTE path, never reconstructed by the
# worker from $CLAUDE_PROJECT_DIR. ROOT CAUSE this locks: $CLAUDE_PROJECT_DIR is UNSET in the Bash-tool shell
# (it is injected only into HOOK commands), so a §4 contract that says `--pidfile = $CLAUDE_PROJECT_DIR/.polish/
# .bg-pids` collapses to `/.polish/.bg-pids` in the worker → run-detach's makedirs('/.polish') crashes, the run
# never fires detached, and (the W27 real-run symptom) the worker improvises a foreground/synchronous science
# run. Fix: the goal builder bakes <PIDFILE> = ${PROJECT_DIR}/.polish/.bg-pids (absolute) and the worker uses it
# VERBATIM — so WRITER (worker) == READER (the asyncRewake hook) even with the empty var. Run: bash tests/t41_detach_pidfile_contract.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROTO="$ROOT/plugins/experiment-lab-ar/spec/experiment-protocol.md"
RESEARCH="$ROOT/spec/research.js"
REWAKE="$ROOT/plugins/paper-polish-ar/hooks/rewake-when-done.sh"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }

# 1. The §4 detach INSTRUCTION must use the baked placeholder, NOT the bare var.
grep -qF -- '--pidfile = <PIDFILE>' "$PROTO" \
  && ok "§4 detach contract instructs --pidfile = <PIDFILE>" \
  || no "§4 detach contract no longer says '--pidfile = <PIDFILE>'"
# The buggy instruction form `--pidfile = $CLAUDE_PROJECT_DIR...` must be GONE (it may still appear inside the
# explanatory 'do NOT rebuild from $CLAUDE_PROJECT_DIR' warning, but never as the --pidfile assignment).
grep -qF -- '--pidfile = $CLAUDE_PROJECT_DIR' "$PROTO" \
  && no "§4 still instructs the broken '--pidfile = \$CLAUDE_PROJECT_DIR' (bare, unset-in-Bash-tool)" \
  || ok "§4 no longer instructs the broken bare-\$CLAUDE_PROJECT_DIR pidfile"

# 2. The MAINTAINER NOTE must advertise <PIDFILE> as a loader-substituted placeholder (else the loader & doc drift).
grep -qF '<PIDFILE>' "$PROTO" && grep -q 'loader substitutes' "$PROTO" \
  && ok "MAINTAINER NOTE lists <PIDFILE> as a substituted placeholder" \
  || no "MAINTAINER NOTE does not advertise <PIDFILE>"

# 3. The goal builder must bake <PIDFILE> = the SAME ${PROJECT_DIR}/.polish/.bg-pids path the hook reads.
grep -qF '<PIDFILE> = ${PROJECT_DIR}/.polish/.bg-pids' "$RESEARCH" \
  && ok "research.js goal builder bakes <PIDFILE> = \${PROJECT_DIR}/.polish/.bg-pids (absolute)" \
  || no "research.js goal builder does not bake the absolute <PIDFILE>"

# 4. WRITER == READER: the hook anchors the pidfile at <root>/.polish/.bg-pids with root=${CLAUDE_PROJECT_DIR:-$PWD}
#    (= PROJECT_DIR). Confirm the hook's literal so this test fails loudly if the vendored hook path ever drifts.
grep -qF 'proj="${CLAUDE_PROJECT_DIR:-$PWD}"' "$REWAKE" && grep -qF 'pidfile="$proj/.polish/.bg-pids"' "$REWAKE" \
  && ok "rewake hook reads \${CLAUDE_PROJECT_DIR:-\$PWD}/.polish/.bg-pids (same anchor the goal builder bakes)" \
  || no "rewake hook pidfile anchor drifted from <root>/.polish/.bg-pids"

# 5. DEMONSTRATION — the bug is deterministic: an unset CLAUDE_PROJECT_DIR makes the BARE form collapse to a
#    root-level path whose dirname is uncreatable.
buggy="$(CLAUDE_PROJECT_DIR=""; echo "$CLAUDE_PROJECT_DIR/.polish/.bg-pids")"
[ "$buggy" = "/.polish/.bg-pids" ] \
  && ok "bare \$CLAUDE_PROJECT_DIR (unset) collapses to /.polish/.bg-pids → makedirs('/.polish') would crash" \
  || no "unexpected bare-var expansion: '$buggy'"

# 6. END-TO-END — with CLAUDE_PROJECT_DIR UNSET (the worker's real condition), the baked absolute pidfile is
#    found by the REAL vendored hook. L0 bakes <PIDFILE>=$PROJECT_DIR/.polish/.bg-pids; the worker writes a PID
#    there; the hook (proj=${CLAUDE_PROJECT_DIR:-$PWD}, cwd=$PROJECT_DIR) OS-waits THAT file and exits 2.
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
PROJECT_DIR="$TMP"                                  # L0's concrete absolute data root
baked="$PROJECT_DIR/.polish/.bg-pids"               # what the goal builder bakes into <PIDFILE>
mkdir -p "$(dirname "$baked")"                       # worker side: run-detach makedirs — succeeds (absolute, writable)
PID="$(python3 - "$PROJECT_DIR" <<'PY'
import sys, subprocess
p = subprocess.Popen(["sh","-c","sleep 2; echo OK > '%s/marker.txt'" % sys.argv[1]], start_new_session=True)
print(p.pid)
PY
)"
echo "$PID" > "$baked"
# Hook runs with CLAUDE_PROJECT_DIR UNSET but cwd = PROJECT_DIR → proj falls back to $PWD = PROJECT_DIR == writer's root.
( cd "$PROJECT_DIR" && env -u CLAUDE_PROJECT_DIR bash "$REWAKE" >/dev/null 2>&1 ); rc=$?
if [ "$rc" = 2 ] && [ -f "$PROJECT_DIR/marker.txt" ] && [ ! -f "$baked" ]; then
  ok "baked absolute pidfile is found+waited by the hook with CLAUDE_PROJECT_DIR unset (writer == reader)"
else
  no "writer/reader mismatch under unset CLAUDE_PROJECT_DIR (rc=$rc, marker=$( [ -f "$PROJECT_DIR/marker.txt" ] && echo y || echo n ), pidfile_cleared=$( [ ! -f "$baked" ] && echo y || echo n ))"
fi

echo "----"; echo "t41_detach_pidfile_contract: $pass passed, $fail failed"; [ "$fail" = 0 ]
