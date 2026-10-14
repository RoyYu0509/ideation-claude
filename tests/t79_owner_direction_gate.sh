#!/usr/bin/env bash
# t79_owner_direction_gate.sh — the owner takes back the research-DIRECTION calls (2026-09-12).
#
# Why: across the real runs the loop never killed an idea through its own evaluation, rescue answered "retained"
# with wording-only residuals, and the amplifier could not be steered. Every kill-capable gate auto-resolved to its
# non-kill default (test-3: viability Continue r1–r5, terminal cap_exit → Ship). The fix hands the per-round
# direction call and the terminal call to the owner, and lets the owner send the amplifier / rescue at a direction.
#
# What this locks:
#   A — WHO answers: gateAnsweredBy(kind) routes gates.owner_kinds to the owner even under adjudicator=agent, in
#       gate() AND main()'s crash-resume path; config default [direction, terminal_gate]; the panel exposes it
#   B — the DIRECTION card: rounds ≥1 use kind 'direction', report the round's kill / rescue / amplify signals, and
#       add round_action {No subagent / Amplify / Rescue}; no question on the direction or terminal card has > 4
#       options (the AskUserQuestion cap)
#   C — ingest: Amplify / Rescue run runOwnerSteer FIRST (Abandon wins), fold, re-present; a round ≥1 Abandon
#       writes FINAL-REPORT-killed.md
#   D — the owner's direction is BINDING: amplifier / rescue goals + skills say "author the work order anyway"
#   E — viability folds into the direction card (returns before its own gate() when direction is owner-answered)
#   F — terminal card: Amplify one more round; a clean exit reaches the owner; clean_exit Ship records verify_final
#   G — the agent rubric: a direction rule, and the agent never picks the owner-only Amplify
#   H — the command doc refuses a standing chat "auto-resolve everything"
# Run: bash tests/t79_owner_direction_gate.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
RUB="$ROOT/spec/spawn-prompts/GATE-ADJUDICATION.md"
CMD="$ROOT/commands/auto-research.md"
CFG="$ROOT/config/config.yaml"
KEY="$ROOT/key-config.yaml"
APPLY="$ROOT/bin/apply_key_config.sh"
AMP="$ROOT/skills/research-amplify/SKILL.md"
RES="$ROOT/skills/research-rescue/SKILL.md"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
# has <function> <literal>: the literal occurs inside that top-level JS function (its line up to the next column-0 `}`)
has() { S="$SPEC" N="$1" T="$2" python3 -c "import os,sys;s=open(os.environ['S']).read();i=s.index('function '+os.environ['N']+'(');b=s[i:s.index(chr(10)+'}',i)];sys.exit(0 if os.environ['T'] in b else 1)"; }
# seg <from> <to> <literal...>: every literal occurs between the first <from> and the next <to> (an ingest branch)
seg() { S="$SPEC" A="$1" B="$2" python3 - "${@:3}" <<'PY'
import os,sys
s=open(os.environ['S']).read(); a=s.index(os.environ['A']); b=s.index(os.environ['B'], a+1); x=s[a:b]
sys.exit(0 if all(t in x for t in sys.argv[1:]) else 1)
PY
}

T_REC="reason === 'clean_exit' || reason === 'cap_exit' ? 'Ship' : reason === 'over_claim' ? 'Ship' : 'Abandon'"   # the terminal gate's per-reason default (also F): only a dead claim abandons
# ── A — who answers ────────────────────────────────────────────────────────────────────────────────
chk "A gateAnsweredBy is defined"                          "grep -qF 'function gateAnsweredBy(kind) {' '$SPEC'"
chk "A adjudicator=owner still means every gate"           "has gateAnsweredBy \"=== 'owner') return 'owner'\""
chk "A owner_kinds consulted under agent"                  "has gateAnsweredBy 'CFG.gates.owner_kinds'"
chk "A gate() routes through gateAnsweredBy"               "has gate 'if (gateAnsweredBy(kind) === '"
chk "A crash-resume never re-adjudicates an owner gate"    "grep -qF 'if (gateAnsweredBy(_g.kind) === ' '$SPEC'"
chk "A config default owner_kinds = [direction]"         "grep -qE '^  owner_kinds: \[direction\]$' '$CFG'"
chk "A control panel exposes owner_gates"                  "grep -qE '^  owner_gates: +\[direction\] ' '$KEY'"
chk "A panel maps owner_gates → gates.owner_kinds"         "grep -qF '\"gates.owner_kinds\"' '$APPLY'"
# (2026-09-23) the loop's exit is a RULE: terminal_gate takes its own default — no card, no judge
chk "A config default default_kinds = [terminal_gate]"    "grep -qE '^  default_kinds: \[terminal_gate\]$' '$CFG'"
chk "A control panel exposes default_gates"                "grep -qE '^  default_gates: +\[terminal_gate\] ' '$KEY'"
chk "A panel maps default_gates → gates.default_kinds"     "grep -qF '\"gates.default_kinds\"' '$APPLY'"
chk "A owner_kinds wins over default_kinds"                "S='$SPEC' python3 -c \"import os,sys;s=open(os.environ['S']).read();i=s.index('function gateAnsweredBy(');b=s[i:s.index(chr(10)+'}',i)];sys.exit(0 if b.index('owner_kinds')<b.index('default_kinds') else 1)\""
chk "A gate() applies the default in-turn, no judge"       "has gate \"if (gateAnsweredBy(kind) === 'default')\" && has gate 'defaultGateAnswer(id, kind, questions)'"
chk "A the default is the gate's own recommended option"   "has defaultGateAnswer 'conservativeOption(q)' && ! has defaultGateAnswer 'spawnL2('"
chk "A crash-resume re-applies a default kind (never blind)" "grep -qF 'defaultGateAnswer(_g.id, _g.kind, _qs)' '$SPEC' && grep -qF '} else if (_qs && _qs.length) {' '$SPEC'"
chk "A the command doc knows the default-answered path"   "grep -qF 'Default-answered (a kind in \`default_kinds\`' '$CMD'"
chk "A default terminal exit: dead claim → Abandon, not killed (clean/cap/over-claim) → Ship = hand back" 'has runTerminalGate "$T_REC"'
chk "A the cap's Ship option reads as a hand-back, not a success" "grep -qF 'Hand back as-is: the central claim was not killed' '$SPEC'"

# ── B — the direction card ─────────────────────────────────────────────────────────────────────────
chk "B rounds ≥1 open kind 'direction' (round 0 stays 'author')" "has gateHandoffApproval \"state.loop_round > 0 ? 'direction' : 'author'\""
chk "B card reports the round's rescue verdicts"          "has gateHandoffApproval 'rescue-verdicts.json'"
chk "B card reports the round's viability brief"          "has gateHandoffApproval '.viability.json'"
chk "B card reports the amplifier's verdict"              "has gateHandoffApproval 'amplify-verdict.json'"
chk "B card reports this card's owner-steer result"       "has gateHandoffApproval 'owner-steer.json'"
chk "B round_action question exists"                      "has gateHandoffApproval \"id: 'round_action'\""
chk "B round_action offers No subagent / Amplify / Rescue" "has gateHandoffApproval \"label: 'No subagent this round'\" && has gateHandoffApproval \"label: 'Amplify (direction in NOTES)'\" && has gateHandoffApproval \"label: 'Rescue (K or concern in NOTES)'\""
chk "B round_action falls back to No subagent"            "has gateHandoffApproval \"recommended: 'No subagent this round'\""
chk "B no question on the direction/terminal card has > 4 options" "S='$SPEC' python3 - <<'PY'
import os,re,sys
s=open(os.environ['S']).read()
def body(n):
    i=s.index('function '+n+'('); return s[i:s.index(chr(10)+'}',i)]
counts=[]
for n in ('gateHandoffApproval','runTerminalGate'):
    for chunk in body(n).split('options: [')[1:]:
        end=re.search(r'\n\s*\]', chunk)
        counts.append(len(re.findall(r\"\{ label: '\", chunk[:end.start()] if end else chunk)))
sys.exit(0 if len(counts) >= 3 and max(counts) <= 4 and min(counts) >= 2 else 1)
PY"

# ── C — ingest ─────────────────────────────────────────────────────────────────────────────────────
H0="id.startsWith('handoff-approve')"; H1="id.startsWith('phase0-')"
chk "C Amplify/Rescue → runOwnerSteer, and Abandon wins"  "seg \"\$H0\" \"\$H1\" \"c !== 'Abandon this idea' && /^(Amplify|Rescue)/.test(act)\" 'runOwnerSteer('"
chk "C the steer runs BEFORE Approve is applied"          "S='$SPEC' python3 - <<'PY'
import os,sys
s=open(os.environ['S']).read(); a=s.index(\"id.startsWith('handoff-approve')\"); x=s[a:s.index(\"id.startsWith('phase0-')\",a)]
sys.exit(0 if 0 <= x.index('runOwnerSteer(') < x.index(\"if (c === 'Approve & run')\") else 1)
PY"
chk "C an authored steer is folded, then the card re-presents" "seg \"\$H0\" \"\$H1\" 'foldOwnerSteer(state)' \"state.stage = 'handoff_gate'\""
chk "C a round ≥1 Abandon writes FINAL-REPORT-killed.md"  "seg \"\$H0\" \"\$H1\" 'writeKilledReport(state, state.loop_round - 1'"
chk "C viability Kill shares the killed-report writer"    "grep -qF \"writeKilledReport(state, state.loop_round, 'viability_killed')\" '$SPEC'"
T_SNAP='snapshot "${ws}" "${state.loop_round}"'
chk "C foldOwnerSteer keys the no-op snapshot on THIS round" 'has foldOwnerSteer "$T_SNAP"'
chk "C foldOwnerSteer folds through the transition path"  "has foldOwnerSteer 'generateHandoff(state, true)'"
chk "C a card-time re-author keeps its SPEC version (owner steer)" "has foldOwnerSteer 'restampSpecVersion(state'"
chk "C a card-time re-author keeps its SPEC version (Revise)" "grep -qF 'restampSpecVersion(state, true)' '$SPEC'"
T_RS='SPEC-v${prev}.md'
chk "C restampSpecVersion writes the just-completed round's slot + re-ledgers it" 'has restampSpecVersion "$T_RS" && has restampSpecVersion "spec_ledger.sh"'

# ── D — the owner's direction is binding ───────────────────────────────────────────────────────────
chk "D the NOTES go verbatim into a direction file"       "has runOwnerSteer 'OWNER_STEER_EOF'"
chk "D the steer is recorded in_flight BEFORE the worker spawns (a detach cannot erase it)" "S='$SPEC' python3 - <<'PY'
import os,sys
s=open(os.environ['S']).read(); i=s.index('function runOwnerSteer('); b=s[i:s.index(chr(10)+'}',i)]
sys.exit(0 if 0 <= b.index(\"status: 'in_flight'\") < b.index('runAmplify(state') else 1)
PY"
chk "D amplifyGoal carries the binding owner scenario"    "has amplifyGoal 'That direction is BINDING'"
chk "D an owner amplify never returns without the order"  "has amplifyGoal 'NEVER returns without that work order'"
chk "D the owner work order is round-scoped"              "has runOwnerSteer 'HANDOFF-amplify-owner-r'"
T_BY="{ by: 'owner' }"
chk "D an owner raise is stamped by: owner"               'has runOwnerSteer "$T_BY"'
chk "D an owner rescue must end in runnable experiment work" "has rescueGoal 'MUST end in a RUNNABLE experiment work order'"
chk "D amplify skill documents the owner-directed scenario" "grep -qF '## 4. Owner-directed amplify' '$AMP'"
chk "D rescue skill documents the owner-directed scenario"  "grep -qF 'owner directed a rescue' '$RES'"

# ── E — viability folds into the direction card ────────────────────────────────────────────────────
FOLD_PY() { S="$1" python3 - <<'PY'
import os,sys
s=open(os.environ['S']).read(); i=s.index('function runViabilityGate('); b=s[i:s.index('\n}',i)]
try:
    a=b.index("gateAnsweredBy('direction') === 'owner'"); g=b.index('gate(state, `viability-gate-')
except ValueError:
    sys.exit(1)
f=b[a:g]
sys.exit(0 if a < g and 'return verdict' in f and 'viability-resolved' in f else 1)
PY
}
chk "E the fold returns before the viability gate() opens" "FOLD_PY '$SPEC'"
T_FOLD="verdict === 'CONTINUE' && CFG.checkpoints.handoff_approval"
chk "E only when a round follows and the card exists"     'has runViabilityGate "$T_FOLD"'
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
sed "s/gateAnsweredBy('direction') === 'owner'/false/" "$SPEC" > "$TMP/neg.js"
chk "E [neg] the fold check FAILS once the fold is gone"  "! FOLD_PY '$TMP/neg.js'"

# ── F — the terminal card ──────────────────────────────────────────────────────────────────────────
T0="id.startsWith('terminal-gate-')"; T1="id.startsWith('audit-artifact-gate-')"
chk "F terminal card offers Amplify one more round"       "grep -qF \"label: 'Amplify one more round'\" '$SPEC'"
chk "F terminal Amplify → runOwnerSteer → transition fold → next round" "seg \"\$T0\" \"\$T1\" '/amplify/i.test(c)' \"runOwnerSteer(state, 'amplify'\" 'generateHandoff(state, true)' 'beginNextRound(state)'"
chk "F terminal Amplify folds BEFORE it advances the counter" "S='$SPEC' python3 - <<'PY'
import os,sys
s=open(os.environ['S']).read(); a=s.index(\"id.startsWith('terminal-gate-')\"); x=s[a:s.index(\"id.startsWith('audit-artifact-gate-')\",a)]
k=x.index('/amplify/i.test(c)'); y=x[k:]
sys.exit(0 if y.index('generateHandoff(state, true)') < y.index('beginNextRound(state)') < y.index(\"'handoff_gate'\") else 1)
PY"
T_CE="runTerminalGate(state, 'clean_exit')"; T_CEO="gateAnsweredBy('terminal_gate') === 'owner'"
chk "F a clean exit reaches the owner's terminal card"    'has runVerify "$T_CE" && has runVerify "$T_CEO"'
chk "F clean_exit defaults to Ship"                       'has runTerminalGate "$T_REC"'
chk "F clean_exit Ship records verify_final like the auto path" "seg \"\$T0\" \"\$T1\" \"/ship/i.test(c) && reason === 'clean_exit'\" 'ambition_reconciled: true, ambition_gaps: 0'"
chk "F clean_exit Abandon has its own exit reason"        "grep -qF \"'owner_abandoned_at_clean_exit'\" '$SPEC'"
T_NEG="reason === 'negative_result' ? [] : ["
chk "F a dead central claim is never offered Amplify"     'has runTerminalGate "$T_NEG"'
chk "F …and the ingest refuses it for a dead claim"       "seg \"\$T0\" \"\$T1\" \"/amplify/i.test(c) && reason !== 'negative_result'\""

# ── G — the agent rubric ───────────────────────────────────────────────────────────────────────────
chk "G rubric knows the direction kind"                   "grep -qF 'author | direction | viability_gate | terminal_gate' '$RUB'"
chk "G rubric: the agent answers round_action No subagent" "grep -qF '\`round_action\` with \"No subagent this' '$RUB'"
chk "G rubric: the agent never picks Amplify one more round" "grep -qF 'Never choose \"Amplify one more round\"' '$RUB'"

# ── H — the command doc ────────────────────────────────────────────────────────────────────────────
chk "H a standing chat auto-resolve is not honoured"      "grep -qF 'NOT honoured for an owner kind' '$CMD'"
chk "H the direction card carries two questions"          "grep -qF 'carries TWO questions' '$CMD'"
chk "H spec still parses"                                 "node --check '$SPEC'"

# ── I — GATE-1 is always the owner's, and lists EVERY verified survivor (2026-09-12) ─────────────────
chk "I GATE-1 opens kind seed_select"                     "grep -qF \"gate(state, 'GATE1-seed-select', 'seed_select', [\" '$SPEC'"
chk "I seed_select is the owner's before any config is read" "S='$SPEC' python3 - <<'PY'
import os,sys
s=open(os.environ['S']).read(); i=s.index('function gateAnsweredBy('); b=s[i:s.index(chr(10)+'}',i)]
sys.exit(0 if 0 <= b.index(\"kind === 'seed_select') return 'owner'\") < b.index('CFG.gates') else 1)
PY"
chk "I an unanswered idea counts as Skip (reader + command)" "grep -qF 'every idea question left unanswered is Skip' '$SPEC' && grep -qF 'left unanswered counts as Skip' '$CMD'"
chk "I the rubric says GATE-1 never reaches the agent"     "grep -qF 'never reaches you: the owner' '$RUB'"
T_FR="filter(c => c.status === 'converged')[n]"
chk "I each GATE-1 card re-checks ITS OWN survivor's bundle" 'has seedFreshness "$T_FR"'
IDEA="$ROOT/plugins/arxiv-recommender-ar/workflows/arxiv-ideation.js"
T_SURV="cands(paperState(p.arxiv_id), 'converged').map(([key, c], n) => ({ p, key, c, n }))"
chk "I ideation PLAN covers EVERY survivor, not one per converged paper" "grep -qF \"\$T_SURV\" '$IDEA' && ! grep -qF \"cands(ps, 'converged')[0]\" '$IDEA'"
chk "I plans are numbered idea<N> in ledger order"         "grep -qF -e '-idea\${s.n}.md' '$IDEA'"

echo "----------------------------------------"
echo "t79: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
