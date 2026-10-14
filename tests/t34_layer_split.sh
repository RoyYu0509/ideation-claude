#!/usr/bin/env bash
# T34 — L1/L2 layer split (2026-06-22). The pipeline used ONE agent type (auto-research:orchestrator) for two
# different jobs: genuine multi-leaf FAN-OUT (review panel, ideation judges) AND single-context PRODUCTION
# (experiment milestone, dossier maintenance, the writing-engine stages). The latter forced single-context workers to wear an
# orchestrator's tools, which let them collapse (do the work themselves, 0 children) or launder a worker's
# conclusion in a conductor context. Fix: THREE tiers — spawnL1 (auto-research:orchestrator) for true fan-out;
# spawnL2 ('claude') for locked single-context leaves; spawnWorker (auto-research:producing-worker) for a heavy
# role that OWNS its work but may delegate PRODUCTION (experiment), gated by an external verifier. This test pins it.
# Run: bash tests/t34_layer_split.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
ESPEC="$ROOT/plugins/experiment-lab-ar/spec/experiment-protocol.md"
OFIRST="$ROOT/plugins/experiment-lab-ar/spec/failure/operational-first.md"   # operational-first G1-G3 ladder disclosed here (on-demand leaf)
ORCH="$ROOT/agents/orchestrator.md"
PWORKER="$ROOT/agents/producing-worker.md"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── the two thin wrappers over one shared body ────────────────────────────────
chk "spawnAgent shared body defined"                "grep -qF 'function spawnAgent(' '$SPEC'"
chk "spawnL1 wrapper = auto-research:orchestrator"  "grep -qF \"spawnAgent('auto-research:orchestrator', role, goal, opts)\" '$SPEC'"
chk "spawnL2 wrapper = plain 'claude' leaf"         "grep -qF \"spawnAgent('claude', role, goal, opts)\" '$SPEC'"

# ── the MIDDLE tier: spawnWorker = a producing worker (owns work + may delegate PRODUCTION) ───────────
chk "spawnWorker wrapper = auto-research:producing-worker" "grep -qF \"spawnAgent('auto-research:producing-worker', role, goal, opts)\" '$SPEC'"
chk "producing-worker agent type defined"           "test -f '$ROOT/agents/producing-worker.md'"
chk "producing-worker carries the Agent (spawn) tool" "grep -qiE 'tools:.*Agent' '$ROOT/agents/producing-worker.md'"
chk "producing-worker forbids a peer + judge-laundering" "grep -qiF 'Never spawn a peer' '$ROOT/agents/producing-worker.md' && grep -qiF 'launder' '$ROOT/agents/producing-worker.md'"

# ── the NO-NEST guarantee is CAPABILITY-DEFINED: production helpers are auto-research:leaf-worker (general-purpose minus the Agent tool), spawned SERIALLY; the built-in general-purpose (Tools:* => can recurse) is forbidden ──
LWORKER="$ROOT/agents/leaf-worker.md"
chk "leaf-worker agent type defined"                "test -f '$LWORKER'"
chk "leaf-worker is a TERMINAL leaf — carries NO Agent/Task tool" "grep -qiE '^tools:' '$LWORKER' && ! grep -qiE '^tools:.*(Agent|Task)' '$LWORKER'"
chk "leaf-worker keeps full production tools (Write+Bash+WebFetch+WebSearch)" "grep -qiE '^tools:.*Write' '$LWORKER' && grep -qiE '^tools:.*Bash' '$LWORKER' && grep -qiE '^tools:.*WebFetch' '$LWORKER' && grep -qiE '^tools:.*WebSearch' '$LWORKER'"
chk "producing-worker routes production to leaf-worker, NOT general-purpose" "grep -qiF 'auto-research:leaf-worker' '$PWORKER' && ! grep -qiE \"subagent_type: 'general-purpose'\" '$PWORKER'"
chk "producing-worker mandates SERIAL spawning (one at a time, no parallel swarm)" "grep -qiF 'one at a time' '$PWORKER' && grep -qiF 'never a parallel swarm' '$PWORKER'"

# the keyword 'general-purpose' is SCRUBBED from every instruction surface — it lives ONLY in the hook (the ban) + these tests (the absence proof)
chk "no 'general-purpose' spawn-instruction leaks into the agent/spec surfaces" "! grep -rqiF 'general-purpose' '$ROOT/agents' '$SPEC' '$ESPEC'"

# ── the harness-enforced backstop: a PreToolUse hook hard-DENIES the built-in general-purpose spawn + redirects to leaf-worker ──
GUARD="$ROOT/hooks/spawn_guard.sh"
chk "spawn-guard hook exists + executable"          "test -x '$GUARD'"
chk "spawn-guard registered as a Task|Agent PreToolUse hook" "grep -qF 'spawn_guard.sh' '$ROOT/hooks/hooks.json' && grep -qF 'Task|Agent' '$ROOT/hooks/hooks.json'"
chk "spawn-guard DENIES general-purpose and redirects to leaf-worker" "printf '%s' '{\"tool_name\":\"Task\",\"tool_input\":{\"subagent_type\":\"general-purpose\"}}' | bash '$GUARD' | grep -qF '\"permissionDecision\": \"deny\"' && printf '%s' '{\"tool_name\":\"Agent\",\"tool_input\":{\"subagent_type\":\"general-purpose\"}}' | bash '$GUARD' | grep -qiF 'auto-research:leaf-worker'"
chk "spawn-guard ALLOWS leaf-worker (silent, no deny)" "[ -z \"\$(printf '%s' '{\"tool_name\":\"Task\",\"tool_input\":{\"subagent_type\":\"auto-research:leaf-worker\"}}' | bash '$GUARD')\" ]"
chk "spawn-guard ALLOWS Explore + non-spawn tools (silent)" "[ -z \"\$(printf '%s' '{\"tool_name\":\"Task\",\"tool_input\":{\"subagent_type\":\"Explore\"}}' | bash '$GUARD')\" ] && [ -z \"\$(printf '%s' '{\"tool_name\":\"Write\",\"tool_input\":{}}' | bash '$GUARD')\" ]"

# ── single-context worker roles are spawned as LEAVES (spawnL2); the heavier experiment is a producing worker ─
chk "experiment milestone is a PRODUCING WORKER (spawnWorker)" "grep -qE \"spawnWorker\\([^)]*'experiment_worker'\" '$SPEC'"
chk "LITERATURE milestone is a PRODUCING WORKER (spawnWorker literature_worker)" "grep -qE \"spawnWorker\\([^)]*'literature_worker'\" '$SPEC'"
chk "dossier maintainer is a LEAF (spawnL2 dossier_writer)"          "grep -qF \"spawnL2('dossier_writer'\" '$SPEC'"
chk "spec delivery is a LEAF (spawnL2 spec_freezer)" "grep -qF \"spawnL2('spec_freezer'\" '$SPEC'"
# none may be a thin orchestrator (spawnL1); experiment is also NOT a locked leaf (spawnL2)
chk "experiment is NOT spawnL1"                     "! grep -qF \"spawnL1('experiment_worker'\" '$SPEC'"
chk "experiment is NOT a locked spawnL2 leaf"       "! grep -qF \"spawnL2('experiment_worker'\" '$SPEC'"
chk "dossier maintainer is NOT spawnL1"             "! grep -qF \"spawnL1('dossier_writer'\" '$SPEC'"
chk "spec_freezer is NOT spawnL1"                   "! grep -qF \"spawnL1('spec_freezer'\" '$SPEC' && ! grep -qF \"spawnL1('paper_\" '$SPEC'"
# seed->HANDOFF is now a PRODUCING WORKER (decision A: researches + LOCKS the §4b SCALE-CONTRACT, may spawn
# Plan/Explore helpers); its M1 completeness review is an INDEPENDENT L0-spawned leaf (auditor != producer).
# verify is a LEAF by default but escalates to an orchestrator when audit.allow_spawn is flipped on.
chk "seed->HANDOFF is a PRODUCING WORKER (spawnWorker)"             "grep -qF \"spawnWorker('seed_to_handoff'\" '$SPEC'"
chk "M1 scale-contract reviewer is an INDEPENDENT LEAF (spawnL2)" "grep -qF \"spawnL2('scale_contract_reviewer'\" '$SPEC'"
chk "LITERATURE bib auditor is an INDEPENDENT LEAF (spawnL2 literature_reviewer)" "grep -qF \"spawnL2('literature_reviewer'\" '$SPEC'"
chk "verify tier is conditional on audit.allow_spawn" "grep -qF 'function spawnVerifier' '$SPEC' && grep -qF 'AUDIT.allow_spawn ? spawnL1' '$SPEC'"
chk "verify is a LEAF in the lean default (allow_spawn off -> spawnL2)" "grep -qF \"spawnL2('independent_verifier', goal)\" '$SPEC'"

# ── genuine FAN-OUT roles stay orchestrators (spawnL1) ────────────────────────
chk "ideation stays an ORCHESTRATOR (spawnL1)"      "grep -qF \"spawnL1('ideation_orchestrator'\" '$SPEC'"
chk "review stays an ORCHESTRATOR (spawnL1)"        "grep -qF \"spawnL1('review_orchestrator'\" '$SPEC'"
chk "the retired polish-figures orchestrator is gone from L0" "! grep -qF 'polish_figures_orchestrator' '$SPEC'"

# ── experiment-protocol.md is re-voiced as a PRODUCING WORKER; the JUDGMENT-laundering boundary is canonical in producing-worker.md (referenced, not restated, by the protocol) ──
chk "experiment-protocol declares EXPERIMENT PRODUCING WORKER" "grep -qF 'EXPERIMENT PRODUCING WORKER' '$ESPEC'"
# production helpers route through auto-research:leaf-worker (general-purpose minus the Agent tool => cannot nest), spawned SERIALLY — never the built-in general-purpose (Tools:* => would recurse into an unbounded spawn tree)
chk "experiment-protocol delegates production via auto-research:leaf-worker" "grep -qiF 'auto-research:leaf-worker' '$ESPEC'"
chk "experiment-protocol does NOT route production via the nesting general-purpose type" "! grep -qiF 'general-purpose' '$ESPEC'"
chk "producing-worker.md (canonical) forbids laundering own judgment" "grep -qiF 'never launder your own judgment' '$PWORKER'"
chk "experiment-protocol references the standing spawn contract (not restates it)" "grep -qiF 'producing-worker spawn contract' '$ESPEC'"
chk "experiment-protocol drops the old experiment_worker fan-out" "! grep -qF 'spawn ONE experiment_worker' '$ESPEC'"
chk "experiment-protocol drops the old reader/interpreter fan-out" "! grep -qiF 'spawn reader/interpreter workers' '$ESPEC'"
chk "experiment-protocol drops dead section_drafter block"        "! grep -qiF 'section_drafter' '$ESPEC'"

# ── but the detach / no-polling invariant is fully PRESERVED in the producing-worker spec ──
chk "leaf still fires DETACHED (run-detach)"        "grep -qF 'run-detach' '$ESPEC'"
chk "leaf still returns long_run_fired + ends turn" "grep -qF \"long_run_fired\" '$ESPEC'"
chk "leaf still waits via .bg-pids (session-level)" "grep -qF '.bg-pids' '$ESPEC'"
chk "operational-first leaf preserves the G1-G3 ladder" "grep -qF '(G1)' '$OFIRST' && grep -qF '(G3)' '$OFIRST'"
chk "experiment-protocol routes S1/S2 to the operational-first leaf" "grep -qiF 'operational-first.md' '$ESPEC'"

# ── the orchestrator agent forbids spawning a peer of itself (P3) ─────────────
chk "orchestrator.md forbids a peer orchestrator"   "grep -qiF 'never spawn a peer' '$ORCH' || grep -qiF 'NEVER spawn a peer' '$ORCH'"

# ── whole spec still parses ───────────────────────────────────────────────────
chk "spec parses (node --check)"                    "node --check '$SPEC'"

echo "----"; echo "t34_layer_split: $pass passed, $fail failed"; [ "$fail" = 0 ]
