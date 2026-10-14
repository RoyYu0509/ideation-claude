#!/usr/bin/env bash
# T50 — INDEPENDENT ideation-content integrity auditor (P3#11, 2026-07-01). The ideation L1 return is checked ONLY
# for ENVELOPE SHAPE (bin/validate_envelope.sh, structural) — so a producer under overload could return a
# STRUCTURALLY-valid envelope pointing at PLACEHOLDER/FABRICATED refined seeds (generic filler, self-admitted
# stubs, invented arXiv IDs, an idea with no evidence sidecar on disk) and sail straight to GATE-1, where the
# owner picks ONE seed to spend DAYS on. Fix: phaseIdeation spawns an INDEPENDENT read-only auditor AFTER the
# envelope validates + BEFORE seed_gate; it writes a per-idea REAL-vs-SUSPECT verdict to disk, and gateSeedSelect
# folds that sidecar into the GATE-1 card context (gate-preview SEAM) so any suspect flag is SHOWN to the owner.
# LEAN DISCIPLINE: the JUDGMENT lives in the asset rubric + the read-only leaf; research.js stays a THIN spec that
# only spawns the auditor + threads the verdict path into the gate context. This test pins the wiring.
# HARDENING (2026-07-01, adversarial review of P3#11): three confirmed holes are now closed + pinned below —
#   (1) fail-open silent-null → a THREE-STATE record ('UNVERIFIED' sentinel when the auditor DID NOT run);
#   (2) id-join is PINNED (context.id = the bare .md stem; no unpinned 'idea-' prefix-stripping);
#   (3) COVERAGE reconciliation (ideation_integrity_covered) so an empty/mis-pathed dir can't read as CLEAN.
# Run: bash tests/t50_ideation_integrity.sh   (also registered in tests/run_all.sh — runs in the full suite)
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
ASSET="$ROOT/spec/spawn-prompts/IDEATION-INTEGRITY.md"
CFG="$ROOT/config/config.yaml"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── thin JS wiring: goal-builder POINTER (no inlined rubric) + the auditor spawn ────────────────────────
chk "goal-builder ideationIntegrityGoal defined"              "grep -qF 'function ideationIntegrityGoal(' '$SPEC'"
chk "goal-builder references the rubric DIRECTLY (spec/spawn-prompts/, no config indirection)" "grep -qF 'spec/spawn-prompts/IDEATION-INTEGRITY.md' '$SPEC'"
chk "goal-builder is a thin POINTER (reads the asset, no inlined rubric)" "grep -qF 'IDEATION-INTEGRITY.md. READ IT FIRST' '$SPEC'"
chk "auditor is an INDEPENDENT LEAF (spawnL2 ideation_auditor)"  "grep -qF \"spawnL2('ideation_auditor'\" '$SPEC'"
chk "the [[SEAM]] marks it an ideation integrity check (LLM judgment, surfaced at GATE-1)" "grep -qF '[[SEAM:ideation-integrity]]' '$SPEC'"

# ── ORDER: the auditor fires AFTER envelope validation (the ideation_orchestrator return) and BEFORE seed_gate ──
ORCH=$(grep -n "spawnL1('ideation_orchestrator'" "$SPEC" | head -1 | cut -d: -f1)
AUD=$(grep -n  "spawnL2('ideation_auditor'"       "$SPEC" | head -1 | cut -d: -f1)
# NOTE: the FIRST "state.stage = 'seed_gate'" in the file is the seed-verify Redirect ingest branch
# (ingestGateAnswer, 2026-07-08) — anchor on the phaseIdeation advance, i.e. the first occurrence AFTER the
# auditor spawn, or the two ORDER assertions below compare against the wrong line.
GATE=$(grep -n "state.stage = 'seed_gate'"         "$SPEC" | awk -F: -v a="${AUD:-0}" '$1 > a' | head -1 | cut -d: -f1)
chk "auditor spawns AFTER the ideation L1 return (envelope already validated in spawnAgent)" "[ -n '$ORCH' ] && [ -n '$AUD' ] && [ '$ORCH' -lt '$AUD' ]"
chk "auditor spawns BEFORE the advance to seed_gate"                                          "[ -n '$AUD' ] && [ -n '$GATE' ] && [ '$AUD' -lt '$GATE' ]"

# ── verdict is WRITTEN TO DISK (.integrity.json) and RECORDED on state for the gate to read ─────────────
chk "verdict path is the .integrity.json sidecar"            "grep -qF '.integrity.json' '$SPEC'"
chk "phaseIdeation records the verdict path on state"        "grep -qF 'state.ideation_integrity = ' '$SPEC'"
chk "verdict dir derived from the ideation artifacts (ideationDir)" "grep -qF 'ideationDir(env.artifacts)' '$SPEC'"

# ── the verdict path FLOWS INTO the seed_gate (GATE-1) card context ─────────────────────────────────────
GSEL=$(grep -n "function gateSeedSelect(" "$SPEC" | head -1 | cut -d: -f1)
INTG=$(grep -n "integrity: state.ideation_integrity" "$SPEC" | head -1 | cut -d: -f1)
chk "GATE-1 per-idea context carries the integrity sidecar (integrity: state.ideation_integrity)" "grep -qF 'integrity: state.ideation_integrity' '$SPEC'"
chk "the integrity context lives INSIDE gateSeedSelect (flows into the GATE-1 card)" "[ -n '$GSEL' ] && [ -n '$INTG' ] && [ '$GSEL' -lt '$INTG' ]"

# ── risk #1 — THREE-STATE record (no fail-open silent-null): a did-not-run auditor gets the 'UNVERIFIED' SENTINEL,
#      NOT a null (null renders identically to "nothing suspect"); GATE-1 must be able to tell CLEAN from UNCHECKED. ─
SENT=$(grep -n "state.ideation_integrity = verdict ? integrity : 'UNVERIFIED'" "$SPEC" | head -1 | cut -d: -f1)
chk "risk#1 phaseIdeation records the 'UNVERIFIED' sentinel (three-state, not null)" "grep -qF \"state.ideation_integrity = verdict ? integrity : 'UNVERIFIED'\" '$SPEC'"
chk "risk#1 the sentinel record sits AFTER the auditor spawn and BEFORE seed_gate" "[ -n '$AUD' ] && [ -n '$SENT' ] && [ -n '$GATE' ] && [ '$AUD' -lt '$SENT' ] && [ '$SENT' -lt '$GATE' ]"
chk "risk#1 the SEAM instructs L0 to surface 'did NOT run — unverified' (not silently clean)" "grep -qiF 'did NOT run' '$SPEC' && grep -qiF 'unverified' '$SPEC'"

# ── risk #2 — id-join is PINNED: the card matches the sidecar's per-idea entry by entry.id === context.id (the bare
#      .md stem), NOT by unpinned+untested 'idea-' prefix-stripping. parseRefinedSeeds' s.id contract is pinned. ────
IDJOIN=$(grep -n "id: s.id" "$SPEC" | head -1 | cut -d: -f1)
chk "risk#2 GATE-1 per-idea context carries the bare stem (id: s.id) for the join" "grep -qF 'id: s.id' '$SPEC'"
chk "risk#2 the id: s.id join lives INSIDE gateSeedSelect (rides the GATE-1 card)" "[ -n '$GSEL' ] && [ -n '$IDJOIN' ] && [ '$GSEL' -lt '$IDJOIN' ]"
chk "risk#2 the join is PINNED to entry.id === context.id (no prefix-stripping)" "grep -qF 'entry.id === context.id' '$SPEC'"
chk "risk#2 parseRefinedSeeds contract pins s.id = the refined-seed .md FILENAME STEM (the auditor's id)" "grep -qF 'parseRefinedSeeds(artifacts):' '$SPEC' && grep -qiF 'FILENAME STEM' '$SPEC'"

# ── risk #3 — COVERAGE reconciliation: an empty/mis-pathed ideationDir makes the auditor enumerate ZERO ideas →
#      {ideas:[]} → falsely CLEAN. Record the stems the auditor JUDGED; the gate marks any uncovered idea UNVERIFIED. ─
chk "risk#3 phaseIdeation records the coverage set (ideation_integrity_covered)" "grep -qF 'state.ideation_integrity_covered = verdict ? (verdict.ideas || []).map(i => i.id) : []' '$SPEC'"
chk "risk#3 the coverage set flows into the GATE-1 card (covered: state.ideation_integrity_covered)" "grep -qF 'covered: state.ideation_integrity_covered' '$SPEC'"
chk "risk#3 ideationDir doc pins ABSOLUTE / resolve against PROJECT_DIR (auditor is a fresh context)" "grep -qF 'MUST resolve a relative path against PROJECT_DIR' '$SPEC'"

# ── config: the model entry for the new role (matches the surrounding format) ───────────────────────────
chk "models.ideation_auditor present"                        "grep -qF 'ideation_auditor:' '$CFG'"
chk "models.ideation_auditor is sonnet / think null (matches siblings)" "grep -E 'ideation_auditor:[[:space:]]*\{ model: \"sonnet\", think: null \}' '$CFG'"

# ── the JUDGMENT lives in the asset (complexity out of the thin JS) ─────────────────────────────────────
chk "asset exists at the configured path"                    "test -f '$ASSET'"
chk "asset frames a REAL vs PLACEHOLDER/FABRICATED judgment" "grep -qiF 'PLACEHOLDER' '$ASSET' && grep -qiF 'FABRICATED' '$ASSET' && grep -qiF 'REAL' '$ASSET'"
chk "asset checks realness signals (mechanism / citations / evidence sidecar / falsifier)" "grep -qiF 'MECHANISM' '$ASSET' && grep -qiF 'CITATIONS' '$ASSET' && grep -qiF 'EVIDENCE SIDECAR' '$ASSET' && grep -qiF 'FALSIFIER' '$ASSET'"
chk "asset flags stub/placeholder/for-speed markers"         "grep -qiF 'for speed' '$ASSET' && grep -qiF 'TODO' '$ASSET' && grep -qiF 'stub' '$ASSET'"
chk "asset auditor is READ-ONLY (edits nothing, never fabricates)" "grep -qiF 'EDIT NOTHING' '$ASSET' && grep -qiF 'NEVER fabricate' '$ASSET'"
chk "asset returns a PER-IDEA verdict { id, integrity: real|suspect, why }" "grep -qF '\"integrity\": \"real\" | \"suspect\"' '$ASSET' && grep -qF '\"why\"' '$ASSET'"
chk "asset returns an overall any_suspect boolean"           "grep -qF '\"any_suspect\": true | false' '$ASSET'"
chk "asset reads the on-disk refined seeds + per-paper JSON + evidence sidecars" "grep -qF 'refined/*.md' '$ASSET' && grep -qF 'evidence-<arxiv_id>.json' '$ASSET'"

# ── spec still parses ────────────────────────────────────────────────────────────────────────────────────
chk "spec parses (node --check)"                             "node --check '$SPEC'"

echo "----"; echo "t50_ideation_integrity: $pass passed, $fail failed"; [ "$fail" = 0 ]
