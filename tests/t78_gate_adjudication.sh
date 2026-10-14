#!/usr/bin/env bash
# t78_gate_adjudication.sh — the autonomous gate path (2026-09-02: owner elected unattended runs).
#
# What this locks:
#   A — gate() branches on gates.adjudicator and does NOT end the turn under `agent`
#   B — the answer comes from a SEPARATE cold-read context, never from L0 itself (GATE-TAXONOMY §0)
#   C — the judge's answer is VALIDATED against that gate's own options; a bad answer falls back
#       conservatively and is logged, never silently accepted
#   D — the run cannot spin: attempt counting + the converge rule + the terminal-gate Ship restriction
#   E — the audit trail survives (decision file still written + archived, marked as agent-adjudicated)
#   F — the owner path is still reachable in one knob
# Run: bash tests/t78_gate_adjudication.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
RUB="$ROOT/spec/spawn-prompts/GATE-ADJUDICATION.md"
TAX="$ROOT/spec/GATE-TAXONOMY.md"
CMD="$ROOT/commands/auto-research.md"
CFG="$ROOT/config/config.yaml"
KEY="$ROOT/key-config.yaml"
APPLY="$ROOT/bin/apply_key_config.sh"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── A — the branch ──────────────────────────────────────────────────────────────────────────────────
chk "A gate() branches on gates.adjudicator"        "grep -qF 'CFG.gates && CFG.gates.adjudicator' '$SPEC'"
chk "A agent path ingests in-turn (no END_TURN)"    "grep -qF 'ingestGateAnswer(state, adjudicateGate(state, id, kind, questions, file))' '$SPEC'"
chk "A owner path still ends the turn"              "grep -qF 'askUser(questions)' '$SPEC' && grep -qF 'END_TURN()' '$SPEC'"
chk "A crash-resume re-adjudicates, not re-waits"   "grep -qF 'readDecisionQuestions(_g.decision_file)' '$SPEC'"
chk "A readDecisionQuestions is specified"          "grep -qF 'readDecisionQuestions(decision_file)' '$SPEC'"

# ── B — separate context (the anti-self-acquittal invariant) ────────────────────────────────────────
chk "B the judge is a spawned leaf, not L0"         "grep -qF \"spawnL2('gate_adjudicator'\" '$SPEC'"
chk "B rubric exists as a spawn-prompt"             "test -f '$RUB'"
chk "B goal-builder is thin (points at the md)"     "grep -qF 'spec/spawn-prompts/GATE-ADJUDICATION.md' '$SPEC'"
chk "B rubric forbids editing anything but its out" "grep -qiF 'EDIT NOTHING except' '$RUB'"
chk "B rubric states it produced none of the work"  "grep -qiF 'produced none of the work' '$RUB'"
chk "B L0 is told never to answer a gate itself"    "grep -qiF 'never answer a gate yourself' '$CMD'"
chk "B taxonomy lists the adjudicator as acquitter" "grep -qiF 'gate adjudicator' '$TAX'"
chk "B taxonomy keeps the owner path documented"    "grep -qF 'gates.adjudicator: owner' '$TAX'"

# ── C — validation, not trust ───────────────────────────────────────────────────────────────────────
chk "C choices validated against the gate options"  "grep -qF 'labels.indexOf(a.choice) >= 0' '$SPEC'"
chk "C invalid/missing answer logs a fallback"      "grep -qF 'gate_adjudication_fallback' '$SPEC'"
chk "C conservativeOption exists"                   "grep -qF 'function conservativeOption(' '$SPEC'"
chk "C fallback is NOT keyword-matched"             "! grep -qE 'conservativeOption[\\s\\S]{0,400}(abandon\\|kill\\|strip)/i' '$SPEC'"
chk "C fallback prefers recommended then first"     "grep -qF 'if (q.recommended && labels.indexOf(q.recommended) >= 0) return q.recommended' '$SPEC'"
chk "C rubric: only listed options, verbatim"       "grep -qiF 'Choose only from the listed options' '$RUB'"
chk "C rubric demands cited evidence"               "grep -qiF 'Cite what you read' '$RUB'"
chk "C rubric: absent evidence -> conservative"     "grep -qiF 'take the conservative option' '$RUB'"

# ── D — the run must converge ───────────────────────────────────────────────────────────────────────
chk "D attempts counted per gate id"                "grep -qF 'state.gate_attempts' '$SPEC'"
chk "D attempt is passed to the judge"              "grep -qF '<ATTEMPT>=' '$SPEC'"
chk "D rubric: no repeat rescue at attempt >= 2"    "grep -qiF 'attempt' '$RUB' && grep -qiF 'Rescue one more round' '$RUB'"
chk "D rubric: attempt >= 3 must end the loop"      "grep -qiF 'ENDS the loop' '$RUB'"
chk "D terminal-gate Ship is restricted"            "grep -qiF 'Ship is the reward-hack path' '$RUB'"
chk "D negative_result Ship is out of scope"        "grep -qiF 'a failure of this role' '$RUB' && grep -qiF \"policy is ABANDON\" '$RUB'"
chk "D viability keeps the no-easy-give-up rule"    "grep -qF '禁止轻易放弃' '$RUB'"

# ── E — audit trail ─────────────────────────────────────────────────────────────────────────────────
chk "E decision file still written at every gate"   "grep -qF 'writeDecisionFile(file' '$SPEC'"
chk "E archived summary marks agent adjudication"   "grep -qF 'adjudicated by agent, attempt' '$SPEC'"
chk "E verdict + evidence logged as an event"       "grep -qF \"logEvent('gate_adjudicated'\" '$SPEC'"
chk "E rationale is required of the judge"          "grep -qF '\"rationale\"' '$RUB'"

# ── F — reversible in one knob ──────────────────────────────────────────────────────────────────────
chk "F config carries gates.adjudicator"            "grep -qF 'adjudicator: agent' '$CFG'"
chk "F control panel exposes it"                    "grep -qF 'gate_adjudicator:' '$KEY'"
chk "F panel maps to the runtime key"               "grep -qF 'gates.adjudicator' '$APPLY'"
chk "F judge has its own model tier"                "grep -qF 'gate_adjudicator:' '$CFG'"
chk "F spec still parses"                           "node --check '$SPEC'"

echo "----------------------------------------"
echo "t78: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
