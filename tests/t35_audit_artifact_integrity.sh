#!/usr/bin/env bash
# T35 — in-round AUDIT-ARTIFACT INTEGRITY gate (2026-06-25). The experiment producing-worker authors its OWN
# gate/sanity/criterion scripts AND the loop's only independent audit landed at the LOOP boundary — so a producer
# that hit a failing gate could, in one internal wave, REWRITE the gate into a pass and fire the downstream waves
# before any auditor != producer ran (the deepgala phase4_gate incident). Fix (spine 1+2+3): the producer REGISTERS
# each audit-artifact in AUDIT-ARTIFACTS.locked.json (L0 owns the sha lock); at every wave boundary L0 re-derives
# the sha (deterministic), and ANY change spawns an INDEPENDENT in-round auditor that classifies legitimate-fix vs
# goalpost-move — a goalpost-move (or an unreadable verdict; FAIL-CLOSED) HARD-BLOCKS the next wave and surfaces.
# LEAN DISCIPLINE: the JUDGMENT lives in the asset rubric + the auditor leaf; the deterministic MECHANICAL work
# (SHA-diff / first-sight lock / git-checkout revert / manifest re-lock) lives in bin/ scripts; research.js stays
# a THIN orchestration spec that only calls them, spawns the auditor, and gates. This test pins the wiring.
# Run: bash tests/t35_audit_artifact_integrity.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
ESPEC="$ROOT/plugins/experiment-lab-ar/spec/experiment-protocol.md"
GINT="$ROOT/plugins/experiment-lab-ar/spec/failure/gate-integrity.md"   # propose!=dispose + single-seed-gate disclosed here (on-demand leaf)
RPROTO="$ROOT/assets/research-protocol.md"
ASSET="$ROOT/spec/spawn-prompts/AUDIT-ARTIFACT-INTEGRITY.md"
CFG="$ROOT/config/config.yaml"
KCFG="$ROOT/key-config.yaml"
PATCHER="$ROOT/bin/apply_key_config.sh"
DIFF="$ROOT/bin/audit_artifact_diff.sh"
DISP="$ROOT/bin/audit_artifact_dispose.sh"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── thin JS wiring: const + goal-builder POINTER (no inlined rubric) + the gate function ───────────────
chk "goal-builder references the rubric DIRECTLY (spec/spawn-prompts/, no config indirection)" "grep -qF 'spec/spawn-prompts/AUDIT-ARTIFACT-INTEGRITY.md' '$SPEC'"
chk "goal-builder auditArtifactReviewGoal defined"  "grep -qF 'function auditArtifactReviewGoal(' '$SPEC'"
chk "goal-builder is a thin POINTER (reads the asset, no inlined rubric)" "grep -qF 'AUDIT-ARTIFACT-INTEGRITY.md. READ IT FIRST' '$SPEC'"
chk "runAuditArtifactGate defined"                  "grep -qF 'function runAuditArtifactGate(' '$SPEC'"

# ── LEAN: the mechanical SHA/git work is OUT of the orchestration spec, IN bin/ scripts ────────────────
chk "research.js does NOT inline the manifest sha-lock fields (moved to bin/)" "! grep -qF 'locked_sha256' '$SPEC'"
chk "research.js does NOT inline a git checkout of a mutation (moved to bin/)" "! grep -qF 'checkout \${mm' '$SPEC'"
chk "research.js CALLS bin/audit_artifact_diff.sh"  "grep -qF 'bin/audit_artifact_diff.sh' '$SPEC'"
chk "research.js CALLS bin/audit_artifact_dispose.sh" "grep -qF 'bin/audit_artifact_dispose.sh' '$SPEC'"

# ── (1) detection bin: deterministic SHA-diff; L0 owns the lock (keyed on L0's own locked_at) ──────────
chk "diff script exists + executable"               "test -x '$DIFF'"
chk "diff reads the producer's manifest"            "grep -qF 'AUDIT-ARTIFACTS.locked.json' '$DIFF'"
chk "diff recomputes sha256 from disk"              "grep -qF 'hashlib.sha256' '$DIFF'"
chk "diff first-sight lock keyed on L0's locked_at (producer cannot pre-seed)" "grep -qF 'locked_at' '$DIFF' && grep -qiF 'FIRST SIGHT' '$DIFF'"
chk "diff prints the mutations JSON"                "grep -qF 'json.dumps(muts)' '$DIFF'"
chk "diff runs clean on an absent manifest ([] )"   "test \"\$(bash '$DIFF' /nonexistent-ws-xyz)\" = '[]'"
chk "diff bad-args exits 2"                         "bash '$DIFF'; [ \$? -eq 2 ]"

# ── (1b) FIRST-SIGHT review (2026-07-18 gap-close) — a criterion/gate's FIRST content is reviewed too,
#     not only later mutations (the E3_conformal_stopping.py `frac_stopped` incident: an ungrounded condition
#     baked in from the artifact's first commit was never a "mutation" and would have silently locked forever) ──
TWS="$(mktemp -d)"; trap 'rm -rf "$TWS"' EXIT
mkdir -p "$TWS/code/exp"
git -C "$TWS/code" init -q; git -C "$TWS/code" config user.email t@t.com; git -C "$TWS/code" config user.name t
printf 'FRAC_STOPPED_FLOOR = 0.5\nverdict = coverage_ok and feasible\n' > "$TWS/code/exp/E3_fake.py"
printf 'def helper(): return 1\n' > "$TWS/code/exp/sanity_fake.py"
git -C "$TWS/code" add -A; git -C "$TWS/code" commit -qm "author wave3 fakes"
cat > "$TWS/AUDIT-ARTIFACTS.locked.json" <<'JSON'
{ "schema": "auto-research-audit-artifacts@1", "artifacts": [
  {"path": "exp/E3_fake.py", "role": "criterion", "criteria_summary": "fake criterion, self-added frac_stopped"},
  {"path": "exp/sanity_fake.py", "role": "sanity", "criteria_summary": "helper lib"}
] }
JSON
FS_OUT="$(bash "$DIFF" "$TWS")"
chk "first-sight: role=criterion IS surfaced for review"        "echo '$FS_OUT' | grep -qF 'exp/E3_fake.py'"
chk "first-sight: surfaced entry is tagged first_sight:true"    "echo '$FS_OUT' | grep -qF '\"first_sight\": true'"
chk "first-sight: role=sanity is NOT surfaced (locks silently)" "! echo '$FS_OUT' | grep -qF 'exp/sanity_fake.py'"
chk "first-sight: both artifacts got locked on disk regardless" "grep -qF 'locked_sha256' \"$TWS/AUDIT-ARTIFACTS.locked.json\" && [ \"\$(grep -c locked_sha256 \"$TWS/AUDIT-ARTIFACTS.locked.json\")\" = 2 ]"
chk "first-sight: re-running with no change now returns []"    "test \"\$(bash \"$DIFF\" \"$TWS\")\" = '[]'"
# dispose: "revert" on a first_sight finding (no was_commit) unlocks + logs to RESEARCH_LOG.md, never crashes
touch "$TWS/RESEARCH_LOG.md"
cat > "$TWS/.round-1.audit-artifact.json" <<JSON
{ "mutated": [ {"path": "exp/E3_fake.py", "role": "criterion", "criteria_summary": "fake criterion, self-added frac_stopped", "was_sha": null, "now_sha": "x", "was_commit": null, "first_sight": true} ], "verdict": {"verdict":"goalpost_move"} }
JSON
chk "dispose revert on a first-sight finding exits 0 (no crash on missing was_commit)" "bash '$DISP' \"$TWS\" revert 1"
chk "dispose revert on first-sight UN-LOCKS the manifest entry"  "python3 -c \"import json; a=[x for x in json.load(open('$TWS/AUDIT-ARTIFACTS.locked.json'))['artifacts'] if x['path']=='exp/E3_fake.py'][0]; exit(0 if 'locked_at' not in a else 1)\""
chk "dispose revert on first-sight leaves sanity artifact's lock untouched" "python3 -c \"import json; a=[x for x in json.load(open('$TWS/AUDIT-ARTIFACTS.locked.json'))['artifacts'] if x['path']=='exp/sanity_fake.py'][0]; exit(0 if 'locked_at' in a else 1)\""
chk "dispose revert on first-sight appends a durable note to RESEARCH_LOG.md" "grep -qF 'STRIP REQUIRED' \"$TWS/RESEARCH_LOG.md\" && grep -qF 'exp/E3_fake.py' \"$TWS/RESEARCH_LOG.md\""
chk "dispose revert on first-sight re-queues it for a FRESH review next diff" "bash '$DIFF' \"$TWS\" | grep -qF 'exp/E3_fake.py'"
rm -rf "$TWS"; trap - EXIT

# ── (2) dispose bin: git-checkout revert / manifest re-lock / first-sight unlock+log ───────────────────
chk "dispose script exists + executable"            "test -x '$DISP'"
chk "dispose revert = git checkout the locked commit" "grep -qF 'checkout' '$DISP' && grep -qF 'was_commit' '$DISP'"
chk "dispose accept = re-lock the manifest shas"    "grep -qF 'locked_sha256' '$DISP' && grep -qF 'now_sha' '$DISP'"
chk "dispose revert branches on missing was_commit (first-sight, nothing to check out)" "grep -qiF 'nothing to check out' '$DISP'"
chk "dispose revert on first-sight logs to RESEARCH_LOG.md" "grep -qF 'RESEARCH_LOG.md' '$DISP'"
chk "dispose bad-args exits 2"                       "bash '$DISP'; [ \$? -eq 2 ]"

# ── (2) disposition orchestration = INDEPENDENT auditor leaf, FAIL-CLOSED, HARD-BLOCK ──────────────────
chk "in-round auditor is an INDEPENDENT LEAF (spawnL2 audit_artifact_auditor)" "grep -qF \"spawnL2('audit_artifact_auditor'\" '$SPEC'"
chk "FAIL-CLOSED: only an affirmative 'legitimate' passes" "grep -qF \"v.verdict === 'legitimate'\" '$SPEC'"
chk "goalpost-move HARD-BLOCKS via gate() + returns 'gated'" "grep -qF \"return 'gated'\" '$SPEC'"
chk "ingest disposes the gate (strip/accept/abandon)" "grep -qF \"id.startsWith('audit-artifact-gate-')\" '$SPEC' && grep -qF '/strip/i.test(c)' '$SPEC'"
chk "gate option relabeled (no prior version to 'revert' TO on first-sight)" "grep -qF 'Strip the flagged condition' '$SPEC'"

# ── (3) call site: fires BEFORE re-spawning the producer for the next wave, AND again before an S1 ─────
#     escalation reaches the owner (a same-turn first-sight artifact is invisible to the FIRST call — see
#     WHY YOU EXIST #2 / the 2026-07-18 E3 incident) — both sites must exist.
chk "call site guards re-spawn (before spawnWorker, !isLit, returns on 'gated')" "grep -qF \"runAuditArtifactGate(state, ws) === 'gated') return\" '$SPEC'"
chk "SECOND call site re-checks before an S1 escalation reaches the owner" "[ \"\$(grep -cF \"runAuditArtifactGate(state, ws) === 'gated') return\" '$SPEC')\" -ge 2 ]"

# ── config: the 4 runtime keys + the key-config control-panel knob ─────────────────────────────────────
chk "checkpoints.audit_artifact_surface present"    "grep -qF 'audit_artifact_surface:' '$CFG'"
chk "models.audit_artifact_auditor present"         "grep -qF 'audit_artifact_auditor:' '$CFG'"
chk "budgets.audit_artifact_audit present"          "grep -qF 'audit_artifact_audit:' '$CFG'"
chk "rubric is NOT a config path (lives in spec/spawn-prompts/, referenced directly)" "! grep -qF 'audit_artifact_integrity_spec:' '$CFG' && test -f '$ASSET'"
chk "key-config exposes the audit_artifact_auditor model knob" "grep -qF 'audit_artifact_auditor:' '$KCFG'"
chk "apply_key_config routes the knob to the runtime config"   "grep -qF 'experiment-review-loop.models.audit_artifact_auditor' '$PATCHER'"

# ── the JUDGMENT lives in the asset (complexity out of the thin JS) ────────────────────────────────────
chk "asset exists at the configured path"           "test -f '$ASSET'"
chk "asset classifies legitimate vs goalpost_move"  "grep -qF 'GOALPOST_MOVE' '$ASSET' && grep -qiF 'LEGITIMATE' '$ASSET'"
chk "asset names the deepgala/phase4_gate incident" "grep -qiF 'phase4_gate' '$ASSET'"
chk "asset extends no-single-sample to internal gates" "grep -qiF 'SINGLE-SAMPLE GATE' '$ASSET'"
chk "asset auditor is READ-ONLY (edits nothing)"    "grep -qiF 'EDIT NOTHING' '$ASSET'"
chk "asset writes a structured verdict JSON"         "grep -qF '\"verdict\": \"legitimate\" | \"goalpost_move\"' '$ASSET'"

# ── (2026-07-18 gap-close) asset covers FIRST-SIGHT review, not only mutations ──────────────────────────
chk "asset names the E3_conformal_stopping/frac_stopped birth-time incident" "grep -qiF 'frac_stopped' '$ASSET' && grep -qiF 'conformal-coverage-control-for-adaptive-irt-testing' '$ASSET'"
chk "asset defines first_sight as a review-worthy event (not just mutations)" "grep -qF 'first_sight' '$ASSET'"
chk "asset: birth-time smuggling is not exempt from self_added_anchor" "grep -qiF 'birth-time smuggling is not exempt' '$ASSET'"
chk "asset: a 'report-labeled' comment does not excuse an ungrounded gating condition" "grep -qiF 'report-only' '$ASSET' || grep -qiF 'report-labeled' '$ASSET'"
chk "asset covers the legitimate self-added-anchor-REMOVAL edit (not misjudged as weaken-to-pass)" "grep -qiF 'self_added_anchor_removal' '$ASSET' || grep -qiF 'SELF-ADDED-ANCHOR REMOVAL' '$ASSET'"

# ── producer spec: typing + lock-at-creation + propose != dispose + single-seed-gate ──────────────────
chk "experiment-protocol: registers audit-artifacts at author time" "grep -qF 'AUDIT-ARTIFACTS.locked.json' '$ESPEC'"
chk "experiment-protocol: producer does NOT write the sha (L0 owns lock)" "grep -qiF 'DO NOT write its' '$ESPEC' && grep -qiF 'L0 OWNS the lock' '$ESPEC'"
chk "experiment-protocol: producer told FIRST content is independently reviewed too" "grep -qiF 'FIRST content of every' '$ESPEC'"
chk "experiment-protocol: producer told to remove (not relabel) a self-added gating condition" "grep -qiF 'REMOVE it from the boolean' '$ESPEC'"
chk "experiment-protocol: producer told to address a STRIP REQUIRED note before trusting a verdict" "grep -qiF 'STRIP REQUIRED' '$ESPEC'"
chk "gate-integrity leaf: propose != dispose for audit-artifacts" "grep -qF 'PROPOSE' '$GINT' && grep -qF 'DISPOSE' '$GINT'"
chk "gate-integrity leaf: single-seed gate FAIL is noise, run the seed floor" "grep -qiF 'single-seed gate' '$GINT'"
chk "gate-integrity leaf: cuts both ways — don't wire in an ungrounded condition at authoring time either" "grep -qiF 'cuts the other way' '$GINT'"
chk "experiment-protocol routes a gate change to the gate-integrity leaf" "grep -qiF 'gate-integrity.md' '$ESPEC'"

# ── constitution: the goalpost invariant ──────────────────────────────────────────────────────────────
chk "research-protocol: 'Never move the goalpost' invariant" "grep -qiF 'Never move the goalpost' '$RPROTO'"

# ── spec still parses ──────────────────────────────────────────────────────────────────────────────────
chk "spec parses (node --check)"                    "node --check '$SPEC'"

echo "----"; echo "t35_audit_artifact_integrity: $pass passed, $fail failed"; [ "$fail" = 0 ]
