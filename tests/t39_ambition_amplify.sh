#!/usr/bin/env bash
# t39 — AMBITION AMPLIFIER (direction #3). Seg 1.2 originally wired the UPWARD amplifier INSIDE verify_final; the
# 2026-06-28 meta-loop restructure (owner 需求 5) MOVED it OUT of verify_final and INTO the loop as a standalone
# maybeAmplify(state), run per-round AFTER review and BEFORE generateHandoff re-authors the work order,
# so an earned raise feeds the SAME regeneration as the round's review demands. Same idiom as t38: research.js is an
# LLM-READ SPEC (AGENT()/spawn never run), so the suite is FUNCTIONAL bin/ tests + STATIC-STRUCTURAL grep on the
# spec/skill/config. The amplifier now gates on THIS round's FOCUSED verify PASS (state.verify_verdict==='PASS' —
# the per-round proxy for "#1 reconciled", so it never amplifies an un-reconciled/over-claimed round) AND loop
# headroom (state.loop_round < CFG.max_loop_rounds) AND once-per-round (a .round-N.amplify-tried marker). On
# can_go_bolder + proposed_raise → raiseAmbitionTarget (writes HANDOFF.ambition.target.json, NEVER the locked floor)
# + return 'raised' (NO recordStage — the loop folds HANDOFF-amplify into the next re-authored work order). The
# TERMINAL verify_final stays the #1 arbiter (auto-earned). #1's verifierGoal reconciles delivery against
# target.json IF it exists, ELSE the locked floor (backward-compat).
#
#   S1 — SKILL: name: research-amplify; OUTPUT contract names can_go_bolder + proposed_raise + at-ceiling; the
#        boundary FORBIDS optimizing for rigor ("more seeds").
#   C1 — config: models: has amplify: + budgets: has amplify:.
#   W1 — wiring: amplifyGoal LOADS `research-amplify` + authors the ROUND-SCOPED HANDOFF-amplify-r<N+1>; runAmplify spawns
#        spawnWorker('amplify'; detach routes onLongRun(state, env, 'AMPLIFY').
#   G1 — THE in-loop gate (load-bearing): standalone maybeAmplify(state) gated on state.verify_verdict==='PASS'
#        (honest round) && state.loop_round < CFG.max_loop_rounds (headroom key MUST be CFG-qualified; a bare/
#        undefined key = a dead amplifier) && !exists(amplifyMark). The can_go_bolder branch calls
#        raiseAmbitionTarget( then returns 'raised' WITHOUT any recordStage(verify_final) (it never ships from the
#        loop); maybeAmplify is CALLED in the loop dispatch before generateHandoff; and the OLD in-verify
#        gate (reconciledFinal && …) is GONE from runVerify, which keeps only its UNCHANGED recordStage(verify_final).
#   T1 — verifierGoal target selection: ambitionFile picks HANDOFF.ambition.target.json when it exists ELSE
#        HANDOFF.ambition.locked.json (the backward-compat fallback).
#   R1 — raiseAmbitionTarget writes HANDOFF.ambition.target.json and a NEGATIVE assert that it does NOT write
#        …locked.json; plus its output shape (central_result/scope/named_rivals/provenance) = what T1's selection reads.
# Each invariant carries a NEGATIVE CONTROL (a mutated copy of the source the assert is meant to catch) proving the
# assert FAILs on the regression — never a tautology.   Run: bash tests/t39_ambition_amplify.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
CFG="$ROOT/config/config.yaml"
SKILL="$ROOT/skills/research-amplify/SKILL.md"
pass=0; fail=0
chk(){ if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# a python helper: assert the standalone maybeAmplify(state) holds the load-bearing shape — the three gate guards
# (honest-round verify PASS + CFG-qualified headroom + per-round marker), the raise path persists the target then
# returns 'raised', and NO recordStage(verify_final) appears ANYWHERE in maybeAmplify (it never ships from the
# loop). Reused on both the live spec and the mutated copies.  usage: GATE_PY <spec-file> → exit 0 iff the shape holds.
GATE_PY(){ S="$1" python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
g=src.find('function maybeAmplify(state) {')
if g<0: sys.exit(1)
end=src.find('\nfunction ', g+1)                      # the maybeAmplify body (up to the next top-level function)
body=src[g:end if end>0 else len(src)]
# the three gate guards (load-bearing: honest-round PASS gate + the CFG-qualified headroom key + the per-round marker)
ok = ("state.verify_verdict !== 'PASS'" in body
      and 'state.loop_round < CFG.max_loop_rounds' in body
      and 'exists(amplifyMark)' in body)
# the raise path persists the target THEN returns 'raised'
raise_=body.find('raiseAmbitionTarget(')
raised=body.find("return 'raised'", raise_ if raise_>0 else 0)
ok = ok and raise_>0 and raised>raise_
# AND maybeAmplify NEVER ship-records (the loop, not the amplifier, owns forward motion)
ok = ok and ("recordStage(state, 'verify_final'" not in body)
sys.exit(0 if ok else 1)
PY
}

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# S1 — the research-amplify SKILL (Seg 1.1): identity + output contract + the anti-rigor boundary.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
chk "S1 SKILL exists"                                   "test -f '$SKILL'"
chk "S1 frontmatter name: research-amplify"             "grep -qF 'name: research-amplify' '$SKILL'"
chk "S1 OUTPUT contract names can_go_bolder"            "grep -qF 'can_go_bolder' '$SKILL'"
chk "S1 OUTPUT contract names proposed_raise"           "grep -qF 'proposed_raise' '$SKILL'"
chk "S1 OUTPUT contract names at-ceiling (honest call)" "grep -qF 'at-ceiling' '$SKILL'"
chk "S1 boundary FORBIDS optimizing for rigor (more seeds)" "grep -qF 'more seeds' '$SKILL'"
# NEGATIVE CONTROL: a skill that lost the anti-rigor boundary (no 'more seeds') FAILs the boundary assert.
SKN="$(mktemp)"; sed 's/more seeds/more SOMETHING/g' "$SKILL" > "$SKN"
chk "S1 [neg] anti-rigor assert FAILs if 'more seeds' boundary removed" "! grep -qF 'more seeds' '$SKN'"
rm -f "$SKN"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# C1 — config: models.amplify + budgets.amplify (the spawnWorker('amplify') role must resolve in BOTH).
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
HASKEY(){ WS="$1" SEC="$2" KEY="$3" python3 - <<'PY'
import os,re,sys
src=open(os.environ['WS']).read().splitlines()
sec=os.environ['SEC']; key=os.environ['KEY']; inb=False
for ln in src:
    if re.match(r'^%s:'%re.escape(sec),ln): inb=True; continue
    if inb and re.match(r'^[A-Za-z_]',ln): inb=False
    if inb and re.match(r'^\s+%s:'%re.escape(key),ln): sys.exit(0)
sys.exit(1)
PY
}
chk "C1 config models: has amplify: key"                "HASKEY '$CFG' models amplify"
chk "C1 config budgets: has amplify: key"               "HASKEY '$CFG' budgets amplify"
# NEGATIVE CONTROL: a config whose models.amplify was renamed away FAILs the models lookup (proves the section-scoped
# matcher is not just a bare grep that would match the budgets.amplify line).
CFN="$(mktemp)"; python3 - "$CFG" "$CFN" <<'PY'
import sys,re
src=open(sys.argv[1]).read().splitlines(); out=[]; inmodels=False
for ln in src:
    if re.match(r'^models:',ln): inmodels=True
    elif re.match(r'^[A-Za-z_]',ln): inmodels=False
    if inmodels and re.match(r'^\s+amplify:',ln): ln=ln.replace('amplify:','amplifyGONE:',1)
    out.append(ln)
open(sys.argv[2],'w').write('\n'.join(out)+'\n')
PY
chk "C1 [neg] models.amplify lookup FAILs if models.amplify renamed (budgets.amplify still present)" "! HASKEY '$CFN' models amplify"
chk "C1 [neg] …and budgets.amplify is UNAFFECTED by that mutation (matcher is section-scoped)" "HASKEY '$CFN' budgets amplify"
rm -f "$CFN"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# W1 — the amplifier wiring: goal loads the skill + authors the HANDOFF; runAmplify spawns the role; detach routes.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# amplifyGoal must name the research-amplify skill AND tell the worker to LOAD it FIRST (a thin-spec goal that POINTS
# to the skill, never inlines the protocol). Substring match via python to dodge the JS template-literal backticks.
chk "W1 amplifyGoal tells the worker to LOAD the skill FIRST" \
    "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find('function amplifyGoal('); j=src.find('\n}',i); body=src[i:j]
sys.exit(0 if ('research-amplify' in body and 'LOAD the' in body and 'skill FIRST' in body) else 1)
PY"
chk "W1 amplifyGoal authors the ROUND-SCOPED HANDOFF-amplify-r<N+1>" "grep -qF 'HANDOFF-amplify-r\${state.loop_round + 1}.md' '$SPEC'"
# the FIXED per-paper name is the regression: generateHandoff mints EXPERIMENTS/<slug of the name>/, so a 2nd raise
# would re-scaffold the segment the 1st already finished (its result.md ⇒ protocol SKIP) and never run.
chk "W1 [neg] the FIXED HANDOFF-amplify-\${state.paper_slug}.md path is GONE" "! grep -qF 'HANDOFF-amplify-\${state.paper_slug}.md' '$SPEC'"
chk "W1 runAmplify spawns the FIXED role spawnWorker('amplify'" "grep -qF \"spawnWorker('amplify'\" '$SPEC'"
# the role passed to spawnWorker must be the FIXED literal 'amplify', NOT a dynamic amplify-\${...} template (the
# class of crash t38's D1 catches for rescue). HANDOFF-amplify-\${...} is a FILE path, not a role — scope to spawn.
chk "W1 spawn role is NOT a dynamic spawnWorker('amplify-\${...}' template" "! grep -qF \"spawnWorker('amplify-\" '$SPEC'"
chk "W1 detached amplify → onLongRun(state, env, 'AMPLIFY')" "grep -qF \"onLongRun(state, env, 'AMPLIFY')\" '$SPEC'"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# G1 — THE in-loop gate (the load-bearing wiring, MOVED out of verify_final 2026-06-28). The amplifier is now the
#      standalone maybeAmplify(state), gated on the HONEST-round proxy (state.verify_verdict==='PASS') + CFG-qualified
#      headroom + the per-round marker; the raise path returns 'raised' WITHOUT shipping; it is CALLED in the loop
#      before generateHandoff; and the OLD in-verify gate is GONE from runVerify.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
chk "G1 marker is per-round .round-\${loop_round}.amplify-tried" \
    "grep -qF 'const amplifyMark = \`\${ws}/.round-\${state.loop_round}.amplify-tried\`' '$SPEC'"
chk "G1 amplifier MOVED into the loop: standalone function maybeAmplify(state)" \
    "grep -qF 'function maybeAmplify(state) {' '$SPEC'"
chk "G1 honest-round gate: state.verify_verdict === 'PASS' (the per-round #1-reconciled proxy)" \
    "grep -qF \"if (state.verify_verdict !== 'PASS') return 'none'\" '$SPEC'"
chk "G1 headroom guard is CFG.max_loop_rounds (NOT a bare max_loop_rounds)" \
    "grep -qF 'if (!(state.loop_round < CFG.max_loop_rounds)) return' '$SPEC'"
chk "G1 raise branch calls raiseAmbitionTarget(ws, a.proposed_raise, state.loop_round)" \
    "grep -qF 'raiseAmbitionTarget(ws, a.proposed_raise, state.loop_round)' '$SPEC'"
chk "G1 raise branch returns 'raised' (folded by the next merge, NOT shipped)" \
    "grep -qF \"return 'raised'\" '$SPEC'"
chk "G1 maybeAmplify is CALLED in the loop (after review, before re-author)" \
    "grep -qF 'maybeAmplify(state); if (turnEnded(state)) return' '$SPEC'"
chk "G1 LOAD-BEARING SHAPE: maybeAmplify gate→raise→return 'raised' with NO recordStage(verify_final) inside it" \
    "GATE_PY '$SPEC'"
chk "G1 OLD in-verify gate is GONE from runVerify (amplifier no longer ships from verify_final)" \
    "! grep -qF 'if (reconciledFinal && state.loop_round < CFG.max_loop_rounds && !exists(amplifyMark)) {' '$SPEC'"
chk "G1 verify_final keeps its UNCHANGED recordStage(state, 'verify_final'" \
    "grep -qF \"recordStage(state, 'verify_final', { verdict: 'PASS', round: state.loop_round, ambition_reconciled: reconciledFinal\" '$SPEC'"

# NEGATIVE CONTROL (a): the dead-amplifier regression — the headroom key degraded to a bare `max_loop_rounds`. The
# GATE_PY shape assert must FAIL (the CFG-qualified key clause no longer holds).
SPB="$(mktemp)"; sed 's/if (!(state.loop_round < CFG.max_loop_rounds)) return/if (!(state.loop_round < max_loop_rounds)) return/' "$SPEC" > "$SPB"
chk "G1 [neg] GATE_PY FAILs if headroom key degraded to a bare max_loop_rounds (dead-amplifier)" "! GATE_PY '$SPB'"
rm -f "$SPB"

# NEGATIVE CONTROL (b): the over-ship bug — maybeAmplify silently records verify_final (it must NEVER ship from the
# loop; the raise is folded into the next re-authored work order and #1 re-audits at the TERMINAL verify_final).
# Inject a recordStage(verify_final) just before maybeAmplify's `return 'raised'` → GATE_PY FAILs (its "no
# recordStage in maybeAmplify" clause catches it).
SPC="$(mktemp)"; python3 - "$SPEC" "$SPC" <<'PY'
import sys
src=open(sys.argv[1]).read()
g=src.find('function maybeAmplify(state) {')
ret=src.find("    return 'raised'", g)
inj="    recordStage(state, 'verify_final', { verdict: 'PASS' }, { commit: false })\n"
out=src[:ret]+inj+src[ret:]
open(sys.argv[2],'w').write(out)
PY
chk "G1 [neg] GATE_PY FAILs if a recordStage(verify_final) is injected into maybeAmplify (over-ship)" "! GATE_PY '$SPC'"
rm -f "$SPC"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# T1 — verifierGoal target selection: target.json IF it exists, ELSE the locked floor (backward-compat fallback).
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
chk "T1 ambitionFile picks target.json when it exists"  "grep -qF 'const ambitionFile = exists(\`\${ws}/HANDOFF.ambition.target.json\`)' '$SPEC'"
chk "T1 ELSE falls back to the locked FLOOR HANDOFF.ambition.locked.json" \
    "grep -qF '? \`\${ws}/HANDOFF.ambition.target.json\` : \`\${ws}/HANDOFF.ambition.locked.json\`' '$SPEC'"
# NEGATIVE CONTROL: if the ELSE fallback were dropped (the ternary degraded so BOTH branches point at target.json),
# the fallback assert FAILs — proving it locks the backward-compat path, not merely the presence of target.json.
SPT="$(mktemp)"; sed 's# : `${ws}/HANDOFF.ambition.locked.json`# : `${ws}/HANDOFF.ambition.target.json`#' "$SPEC" > "$SPT"
chk "T1 [neg] fallback assert FAILs if the locked.json ELSE branch is removed" \
    "! grep -qF '? \`\${ws}/HANDOFF.ambition.target.json\` : \`\${ws}/HANDOFF.ambition.locked.json\`' '$SPT'"
rm -f "$SPT"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# R1 — raiseAmbitionTarget writes target.json (NOT the locked floor) and the persisted shape = what T1 reads.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
chk "R1 raiseAmbitionTarget writes HANDOFF.ambition.target.json" \
    "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find('function raiseAmbitionTarget('); j=src.find('\n}',i)
body=src[i:j]
sys.exit(0 if ('const target = \`\${ws}/HANDOFF.ambition.target.json\`' in body and 'writeJson(target,' in body) else 1)
PY"
chk "R1 [neg] raiseAmbitionTarget does NOT writeJson to …locked.json (immutable floor)" \
    "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find('function raiseAmbitionTarget('); j=src.find('\n}',i)
body=src[i:j]
# fail-closed if it ever writes the locked floor
sys.exit(0 if 'locked.json' not in body else 1)
PY"
chk "R1 persisted shape = central_result/scope/named_rivals/provenance (what T1's #1 selection reads)" \
    "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find('function raiseAmbitionTarget('); j=src.find('\n}',i)
body=src[i:j]
need=['central_result:','scope:','named_rivals:','provenance:']
sys.exit(0 if all(k in body for k in need) else 1)
PY"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# V1 — verdict persistence (quality-ceiling upgrade 2026-07-07): BOTH amplify outcomes land on disk as
# .round-N.amplify-verdict.json (the at-ceiling rationale used to vanish into a bare event line — it is
# /learn's [OPPORTUNITY]-lane headroom signal); runAmplify propagates `earnable`; rescue verdicts persist
# as .round-N.rescue-verdicts.json from runResearchRescue (covers ALL its call sites).
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
AMPV_PY(){ S="$1" python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
g=src.find('function maybeAmplify(state) {')
if g<0: sys.exit(1)
end=src.find('\nfunction ', g+1)
body=src[g:end if end>0 else len(src)]
w=body.find('.amplify-verdict.json')
if w<0: sys.exit(1)
# the writeJson sits AFTER the detach short-circuit and BEFORE the raise branch → both outcomes covered
ok = body.find("return 'detached'") < w < body.find('raiseAmbitionTarget(')
for k in ("schema: 'auto-research-amplify-verdict@1'", "outcome:", "rationale:", "earnable:", "proposed_raise:"):
    ok = ok and (k in body)
sys.exit(0 if ok else 1)
PY
}
chk "V1 maybeAmplify persists .amplify-verdict.json (both outcomes, full shape)" "AMPV_PY '$SPEC'"
chk "V1 runAmplify propagates earnable from metrics.amplify" \
    "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find('function runAmplify('); j=src.find('\nfunction ',i+1)
sys.exit(0 if 'earnable: (a && a.earnable) || null' in src[i:j] else 1)
PY"
# NEGATIVE CONTROL: a spec whose amplify-verdict writeJson was dropped FAILs the shape assert.
SPV="$(mktemp)"; sed 's/\.amplify-verdict\.json/.amplify-verdict-GONE.json/' "$SPEC" > "$SPV"
chk "V1 [neg] shape assert FAILs if the amplify-verdict write is removed" "! AMPV_PY '$SPV'"
rm -f "$SPV"
RESC_PY(){ S="$1" python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
g=src.find('function runResearchRescue(')
if g<0: sys.exit(1)
end=src.find('\nfunction ', g+1)
body=src[g:end if end>0 else len(src)]
w=body.find('.rescue-verdicts.json')
# persisted AFTER the per-item map, with scenario + residual/why_none in the record, then results returned
ok = w>0 and ("schema: 'auto-research-rescue-verdict@1'" in body) and ('scenario' in body) \
     and ('residual:' in body) and ('why_none:' in body) and (body.find('return results') > w)
sys.exit(0 if ok else 1)
PY
}
chk "V1 runResearchRescue persists .rescue-verdicts.json (scenario + residual, all call sites)" "RESC_PY '$SPEC'"
SPR="$(mktemp)"; sed 's/\.rescue-verdicts\.json/.rescue-verdicts-GONE.json/' "$SPEC" > "$SPR"
chk "V1 [neg] rescue assert FAILs if the rescue-verdicts write is removed" "! RESC_PY '$SPR'"
rm -f "$SPR"

# ── spec still parses ────────────────────────────────────────────────────────────────────────────────────
chk "spec parses (node --check)"                       "node --check '$SPEC'"

echo "----"; echo "t39_ambition_amplify: $pass passed, $fail failed"; [ "$fail" = 0 ]
