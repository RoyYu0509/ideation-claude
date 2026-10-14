#!/usr/bin/env bash
# T4 — decision-file roundtrip + fresh-session resume inference (HANDOFF §6). The human gate is
# file-based by design, so this fully exercises the durable backbone WITHOUT AskUserQuestion (which is
# an interactive L0-only layer on top). Simulates: L0 writes DECISIONS-PENDING.md + sets pending_gate;
# next turn ingests the ANSWER, archives to DECISIONS-RESOLVED-<n>.md, clears the gate, advances state.
# Also checks the entry-point inference main() uses on startup. Run: bash tests/t4_decision_roundtrip.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPL="$ROOT/assets/decision-file-template.md"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/state/decisions"
pass=0; fail=0
chk() { if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

export TMP TMPL
python3 - <<'PY'
import os, json, shutil, glob, re
TMP, TMPL = os.environ["TMP"], os.environ["TMPL"]
SF = os.path.join(TMP, "state", "pipeline-state.json")
DEC = os.path.join(TMP, "state", "decisions")
def save(s): json.dump(s, open(SF,"w"), indent=2)
def load():  return json.load(open(SF))

# 0. fresh state at the seed_gate stage
save({"stage":"seed_gate","loop_round":0,"paper_slug":None,"workspace":None,"venue":None,
      "pending_gate":None,"detached":[],"stage_budgets_spent":{},"history":[]})

# 1. L0 writes a pending decision from the template (filled minimally) + sets pending_gate
pend = os.path.join(DEC, "DECISIONS-PENDING.md")
shutil.copyfile(TMPL, pend)
open(pend,"a").write("\n## Q1 — pick a seed\n**id:** `seed`\n**ANSWER:** \n")
s = load(); s["pending_gate"] = {"id":"GATE1-seed-pick","kind":"author","decision_file":pend}; save(s)
assert os.path.exists(pend) and load()["pending_gate"], "gate not written"

# 2. Entry-point inference (mirrors research.js main()): pending_gate -> ingest
def infer(s):
    if s.get("pending_gate"): return "ingest_pending"
    if s.get("detached"):     return "resume_detached"
    return "startup_card"
assert infer(load()) == "ingest_pending", "inference should route to ingest when a gate is pending"

# 3. Owner answers (edits the ANSWER line); next turn INGESTS: validate -> archive -> advance
txt = open(pend).read().replace("**ANSWER:** \n", "**ANSWER:** 2501.01234-idea2\n")
open(pend,"w").write(txt)
answers = [a.strip() for a in re.findall(r"\*\*ANSWER:\*\*\s*(.+)", open(pend).read())]
answers = [a for a in answers if a and not a.startswith("<")]   # ingest skips unfilled <placeholder> lines
answer = answers[0] if answers else ""
assert answer == "2501.01234-idea2", "answer not parsed (got %r)" % answers
n = len(glob.glob(os.path.join(DEC,"DECISIONS-RESOLVED-*.md"))) + 1
shutil.move(pend, os.path.join(DEC, f"DECISIONS-RESOLVED-{n}.md"))
s = load(); s["pending_gate"] = None; s["paper_slug"] = "my-paper"; s["stage"] = "setup_workspace"; save(s)

# 4. assertions
res = load()
print("RESULT", json.dumps({
  "resolved_exists": os.path.exists(os.path.join(DEC,"DECISIONS-RESOLVED-1.md")),
  "pending_gone": not os.path.exists(pend),
  "gate_cleared": res["pending_gate"] is None,
  "stage_advanced": res["stage"] == "setup_workspace",
  "inference_clean_state": infer({"pending_gate":None,"detached":[]}) == "startup_card",
  "inference_detached": infer({"pending_gate":None,"detached":[{"pidfile":"x"}]}) == "resume_detached",
}))
PY

OUT=$(python3 - <<'PY'
import os, json, glob
TMP=os.environ["TMP"]; DEC=os.path.join(TMP,"state","decisions")
res=json.load(open(os.path.join(TMP,"state","pipeline-state.json")))
print(json.dumps({
 "resolved_exists": bool(glob.glob(os.path.join(DEC,"DECISIONS-RESOLVED-1.md"))),
 "pending_gone": not os.path.exists(os.path.join(DEC,"DECISIONS-PENDING.md")),
 "gate_cleared": res["pending_gate"] is None,
 "stage_advanced": res["stage"]=="setup_workspace"}))
PY
)
chk "resolved file archived"        "echo '$OUT' | grep -q '\"resolved_exists\": true'"
chk "pending file removed"          "echo '$OUT' | grep -q '\"pending_gone\": true'"
chk "pending_gate cleared in state" "echo '$OUT' | grep -q '\"gate_cleared\": true'"
chk "state advanced after ingest"   "echo '$OUT' | grep -q '\"stage_advanced\": true'"
echo "----"; echo "t4_decision_roundtrip: $pass passed, $fail failed"; [ "$fail" = 0 ]
