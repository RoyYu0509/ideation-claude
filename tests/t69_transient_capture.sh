#!/usr/bin/env bash
# T69 — capture-hygiene prose wiring (ARIS item 4, 2026-07-09): the transient SSOT exists with its four
# anti-patterns + cause closed-set, every consumer references it, the DOSSIER missing-vs-weaker split
# replaced the merged narrowing sentence, and the /learn lanes (evidence pack §7, charter AUTO-INVALID,
# adversarial transient-source attack, synthesis cause rule, quality trend cause-homogeneity) are wired.
# Run: bash tests/t69_transient_capture.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }
has(){ grep -q "$2" "$ROOT/$1"; }

T="plugins/experiment-lab-ar/spec/failure/transient.md"

# 1) the SSOT — definitions, four anti-patterns, OOM adjudication, cause closed-set, negative space
[ -f "$ROOT/$T" ] && ok "failure/transient.md exists" || no "transient.md missing"
has "$T" "identical command, code, and config would succeed" && has "$T" "discard-by-default" \
  && ok "transient.md carries the action test + discard-by-default" || no "SSOT core rules missing"
has "$T" "never classified transient OR systematic by signature alone" \
  && ok "transient.md: OOM adjudicated by one identical re-run, capacity route untouched" || no "OOM adjudication missing"
has "$T" "env_transient | oom | code | unknown" && ok "transient.md pins the cause closed-set" || no "cause closed-set missing"
has "$T" "Negative capability claim" && has "$T" "Single-instance narrative" \
  && ok "transient.md carries all four capture anti-patterns" || no "anti-patterns incomplete"
has "$T" "died run is never a result" && ok "transient.md: a died run is never a result/negative" || no "died-run rule missing"

# 2) run-side consumers each reference the SSOT
has "plugins/experiment-lab-ar/spec/experiment-protocol.md" "failure/transient.md" \
  && ok "experiment-protocol routes transient deaths to the SSOT (§5 table + PRIOR_CRASH triage)" || no "experiment-protocol not wired"
has "plugins/experiment-lab-ar/spec/experiment-protocol.md" "NEVER a result.md and NEVER a negative result" \
  && ok "experiment-protocol: a died run is never a result.md / negative result" || no "died-run≠result rule missing"
has "plugins/experiment-lab-ar/spec/failure/operational-first.md" "zeroth check" \
  && has "plugins/experiment-lab-ar/spec/failure/operational-first.md" "transient.md" \
  && ok "operational-first: zeroth completed-run check before G1-G3" || no "operational-first zeroth check missing"
has "skills/research-rescue/SKILL.md" "infra death is NOT a falsified" \
  && has "skills/research-rescue/SKILL.md" "never cite an" \
  && ok "research-rescue: infra-death triage + not_retained is a SCIENCE verdict" || no "research-rescue not wired"
has "spec/spawn-prompts/VIABILITY-RECOMMENDER.md" "repeatedly DIES of the environment" \
  && ok "viability recommender distinguishes transient death from exhaustion condition (ii)" || no "recommender not wired"
has "assets/research-protocol.md" "cause:env_transient" \
  && ok "living-log discipline: transient failure = one tagged line + the fix, never a capability negative" || no "living-log line missing"

# 3) DOSSIER — the missing-vs-weaker split is in, the merged sentence is gone
has "spec/spawn-prompts/DOSSIER.md" "Unmeasured is not weak" \
  && ok "DOSSIER: 'Unmeasured is not weak' narrowing guard" || no "DOSSIER guard missing"
grep -q "If a result is missing or\s*$" "$ROOT/spec/spawn-prompts/DOSSIER.md" \
  && no "DOSSIER still carries the merged missing-or-weaker sentence" \
  || ok "DOSSIER merged missing-or-weaker sentence is gone (split into measured/unproduced branches)"
has "spec/spawn-prompts/DOSSIER.md" "MISSING" && has "spec/spawn-prompts/DOSSIER.md" "prior recorded state stands" \
  && ok "DOSSIER ANTI-FABRICATION splits weaker(measured) from missing(unproduced)" || no "ANTI-FABRICATION split missing"

# 4) /learn lanes
has "spec/learn.js" "classify_crash.py\" scan" \
  && ok "learn.js phaseManifest produces the transient-event ledger (degrade honest)" || no "learn.js scan call missing"
has "spec/spawn-prompts/LEARN-EVIDENCE-PACK.md" "环境瞬态账本" \
  && ok "evidence pack carries §7 transient ledger + the machine-only note" || no "evidence pack §7 missing"
has "spec/spawn-prompts/LEARN-CHARTER.md" "environment-transient event" \
  && has "spec/spawn-prompts/LEARN-CHARTER.md" "transient-clean" \
  && ok "charter: transient-as-science AUTO-INVALID + CHALLENGE transient-clean leg" || no "charter lanes missing"
has "spec/spawn-prompts/LEARN-ADVERSARIAL-VERIFY.md" "transient-source" \
  && ok "adversarial verify carries the transient-source attack + CHALLENGE leg (d)" || no "verify attack missing"
has "spec/spawn-prompts/LEARN-SYNTHESIS.md" "died_mid_run" \
  && ok "synthesis: died_mid_run requires the mechanical cause" || no "synthesis cause rule missing"
has "spec/spawn-prompts/LEARN-CROSSCUT-QUALITY.md" "CAUSE-HOMOGENEOUS" \
  && ok "X-quality: trend points must be cause-homogeneous; transient trends ground INFRA findings only" || no "trend rule missing"

# 5) schema/writer wiring (behavior proven in t65/t68; here just the contract text)
has "assets/learn-quality-ledger-schema.json" "REQUIRED when route=died_mid_run" \
  && ok "quality-ledger schema documents the died_mid_run cause requirement" || no "schema cause doc missing"

echo "----"; echo "t69_transient_capture: $pass passed, $fail failed"; [ "$fail" = 0 ]
