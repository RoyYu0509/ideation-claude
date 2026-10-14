#!/usr/bin/env bash
# T11 — FREE-TEXT input contract. The /auto-research entry no longer parses input: L0 captures $ARGUMENTS
# RAW into state.user_input and passes it verbatim to the ideation L1; ALL of its meaning (profile-rebuild
# intent / pinned papers) is owned by the vendored arxiv-scout. The researcher-switch feature was REMOVED.
# This test proves:
#   (1) the researcher-switch L0 machinery is GONE from spec/research.js (no override / profile_setup / parse);
#   (2) state.user_input is captured in main() and threaded into the phaseIdeation goal;
#   (3) commands/auto-research.md advertises free-text and the "L0 NEVER parses" rule;
#   (4) config has no leftover profile_archive key;
#   (5) the researcher-switch logic is GONE from arxiv-scout.js, while pinned-paper detection still classifies;
#   (6) the relocated vendored bin/set_researcher.py still reads the config (--get; ar-init + the --get display still use it).
# All MECHANICAL + offline. Run: bash tests/t11_freetext_input.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
CMD="$ROOT/commands/auto-research.md"
CFG="$ROOT/config/config.yaml"
SCOUT="$ROOT/plugins/arxiv-recommender-ar/workflows/arxiv-scout.js"
SR="$ROOT/plugins/arxiv-recommender-ar/bin/set_researcher.py"
VCFG="$ROOT/plugins/arxiv-recommender-ar/config/config.yaml"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── (1) L0 researcher-switch machinery is GONE ─────────────────────────────────
chk "spec: no researcher_override"           "! grep -q 'researcher_override' '$SPEC'"
chk "spec: no phaseProfileSetup function"     "! grep -q 'phaseProfileSetup' '$SPEC'"
chk "spec: no parseResearcherOverride"        "! grep -q 'parseResearcherOverride' '$SPEC'"
chk "spec: no profile_setup stage/case"       "! grep -qE \"profile_setup\" '$SPEC' || ! grep -qE \"case 'profile_setup'\" '$SPEC'"
chk "spec: stage enum no longer lists profile_setup" "! grep -qE \"'profile_setup'\\|'ideation'\" '$SPEC'"

# ── (2) state.user_input captured in main() + threaded into the ideation goal ──
chk "spec: state.user_input captured from ARGUMENTS in main()" \
    "grep -qE 'state\\.user_input = ARGUMENTS' '$SPEC'"
chk "spec: user_input in the state model comment" \
    "grep -qE '^//[[:space:]]*user_input:' '$SPEC'"
chk "spec: phaseIdeation goal references state.user_input" \
    "awk '/function phaseIdeation/{f=1} f&&/state\\.user_input/{print; exit}' '$SPEC' | grep -q user_input"
chk "spec: still spawns the ideation_orchestrator L1 (plumbing intact)" \
    "grep -q \"spawnL1('ideation_orchestrator'\" '$SPEC'"

# ── (3) command md: free-text contract ────────────────────────────────────────
chk "cmd: argument-hint advertises free-text"  "grep -qiE 'argument-hint:.*free-text' '$CMD'"
chk "cmd: has the 'L0 NEVER parses' rule"       "grep -qi 'NEVER parses' '$CMD'"
chk "cmd: no stale profile_setup / parseResearcherOverride" \
    "! grep -qiE 'profile_setup|parseResearcherOverride' '$CMD'"

# ── (4) config: profile_archive key removed ───────────────────────────────────
chk "config: profile_archive key removed" "! grep -qE '^[[:space:]]*profile_archive:' '$CFG'"

# ── (5) vendored arxiv-scout.js: switch logic REMOVED; pinned detection still classifies ──
chk "scout: no needSwitch"               "! grep -q 'needSwitch' '$SCOUT'"
chk "scout: no switchDirective"          "! grep -q 'switchDirective' '$SCOUT'"
chk "scout: RESEARCHER is const (no switch reassignment)" "grep -qE 'const RESEARCHER' '$SCOUT'"
chk "scout: no longer calls set_researcher.py (switch removed)" "! grep -q 'set_researcher.py' '$SCOUT'"

# detection-regex unit (mirrors the JS that REMAINS): an arXiv URL → pinned; a NON-arXiv URL → ignored
# (no longer a switch); a topic → neither.
chk "scout: pinned detection classifies, non-arXiv URL ignored" "node -e '
function detect(u){
  const aRe=/(?:arxiv\\.org\\/(?:abs|pdf)\\/|arxiv:)(\\d{4}\\.\\d{4,5})(?:v\\d+)?/gi;
  const pin=[]; let m; while((m=aRe.exec(u))!==null) if(!pin.includes(m[1])) pin.push(m[1]);
  return {pin};
}
const a=detect(\"see https://x.edu/~jane s2:999888\");   // non-arXiv URL → NOT pinned, no switch
const b=detect(\"pin https://arxiv.org/abs/2501.12345\");
const c=detect(\"focus on diffusion models this week\");
if(a.pin.length!==0) process.exit(1);
if(!(b.pin[0]===\"2501.12345\")) process.exit(2);
if(c.pin.length!==0) process.exit(3);
'"

# ── (6) relocated vendored set_researcher.py still reads config (offline, no mutation) ──
chk "scout: vendored bin/set_researcher.py exists" "test -f '$SR'"
# --get is READ-ONLY (no mutation), so run it directly on the vendored config — no temp copy / no exit().
chk "scout: set_researcher.py --get returns JSON with personal_website + s2_author_id" \
    "python3 '$SR' --config '$VCFG' --get | python3 -c \"import json,sys; d=json.load(sys.stdin); assert 'personal_website' in d and 's2_author_id' in d\""

echo "----"; echo "t11_freetext_input: $pass passed, $fail failed"; [ "$fail" = 0 ]
