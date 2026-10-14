#!/usr/bin/env bash
# t70 — verified-kill ideation redesign (2026-07-11). Owner mandate: convergence gates on VERIFICATION
# ARTIFACTS (executed probes / replayable prior-art / derivation checks / real listings), NEVER on tier
# scores; content-level failure = pure kill + regeneration, NO successor/rescue channel; seed_verify
# absorbed into the weekly loop. Static-structural grep locks on the specs (same idiom as t40/t58).
#   A — workflow B is the kill loop: stages, ledger, death certificates, no revision loop, no tiers.
#   B — deterministic finalize: '## Verification Record' machine-derived + '## Verified Claim' equality check.
#   C — mechanical layer wired: V0 via Bash (verify_bundle.py), probe contract, bundle validating writer.
#   D — research.js: seed_verify gate GONE (absorbed), parseRefinedSeeds carries the verification contract,
#       GATE-1 rides the zero-token freshness check, HANDOFF folds the Verification Record as binding input.
#   E — kill-path skills exist with the right separations (screen/verify/recheck/refute; auditor != producer).
# Run: bash tests/t70_verification_record.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARX="$ROOT/plugins/arxiv-recommender-ar"
WB="$ARX/workflows/arxiv-ideation.js"
LED="$ARX/scripts/ideation_ledger.py"     # the candidate/paper state machine (mint/V0/bounce moved here)
SPEC="$ROOT/spec/research.js"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── A — the kill loop ───────────────────────────────────────────────────────────────────────────────
chk "A workflow B carries the five stages"            "grep -qF \"phase('Generate')\" '$WB' && grep -qF \"phase('Screen')\" '$WB' && grep -qF \"phase('Verify')\" '$WB' && grep -qF \"phase('Recheck')\" '$WB' && grep -qF \"phase('Plan')\" '$WB'"
chk "A ledger is week-<W>-ideation-ledger.json"       "grep -qF -- '-ideation-ledger.json' '$WB'"
chk "A death certificates minted by the ledger (_mint_certificate)" "grep -qF 'def _mint_certificate(' '$LED'"
chk "A kill-reason taxonomy pinned (retread + integrity; assets no longer kill)" "grep -qF \"'scooped', 'retread'\" '$WB' && grep -qF \"'premise_failed', 'proof_broken'\" '$WB' && ! grep -qF \"'asset_dead'\" '$WB'"
chk "A NO revision loop: no refine rounds, no issue-ledger delta audit" "! grep -qiF 'revision mode' '$WB' && ! grep -qF 'max_refine_rounds' '$WB'"
chk "A NO tier gating anywhere in workflow B"         "! grep -qF 'section_quality_bar' '$WB' && ! grep -qF \"'inadequate', 'developing'\" '$WB'"
chk "A honest exhaustion is a terminal self-DROP"     "grep -qF 'exhausted_honest' '$WB' && grep -qF 'exhaustion_note_zh' '$WB'"
chk "A graveyard feeds regeneration (this week only)" "grep -qF 'ps.graveyard' '$WB' && grep -qF 'graveyard' '$LED'"
chk "A mechanical bounce is one-time and content-frozen" "grep -qF 'bounces' '$LED' && grep -qF 'bundle.prev.json' '$LED' && grep -qiF 'MECHANICAL BOUNCE' '$WB'"
chk "A significance floor demands the confrontation object" "grep -qF 'significance_confrontation' '$WB' && grep -qF 'strongest_rival_row' '$WB'"

# ── B — deterministic finalize blocks ───────────────────────────────────────────────────────────────
chk "B '## Verification Record' is machine-derived (JS block builder)" "grep -qF 'function verificationRecordBlock(' '$WB' && grep -qF \"'## Verification Record'\" '$WB'"
chk "B '## Verified Claim' equality check + canonical overwrite" "grep -qF \"'## Verified Claim'\" '$WB' && grep -qF 'verified_claim_drift' '$WB'"
chk "B the Record inserts BEFORE the /research seed (seed stays byte-compatible)" "grep -qF \"'## /research Seed'\" '$WB'"

# ── C — mechanical layer wiring ─────────────────────────────────────────────────────────────────────
chk "C V0 runs verify_bundle.py from the ledger (zero-token)" "grep -qF 'verify_bundle.py' '$LED' && grep -qF 'def _run_v0(' '$LED'"
chk "C V0 kills on integrity codes, bounces only mechanical ones" "grep -qF 'MECHANICAL_CODES' '$LED'"
# ── 2026-09 evidence rules: a toy may not science-kill ──────────────────────────────────────────────
VER="$ARX/skills/arxiv-verify/SKILL.md"
SCR="$ARX/skills/arxiv-screen/SKILL.md"
chk "F verify carries the instrument test (math vs stand-in measurement)" "grep -qiF 'checking a piece of MATHEMATICS, or' '$VER' && grep -qiF 'do not write it' '$VER'"
chk "F a toy may not science-kill (principle stated, loop cited)"        "grep -qiF 'toy may not science-kill' '$VER' && grep -qiF 'CHEAP TRIAGE' '$VER'"
chk "F verifier-added rows may flag but not kill alone"                  "grep -qiF 'may FLAG but never kill alone' '$VER'"
chk "F rescope is a real outcome (mechanism stands, route does not)"     "grep -qF 'rescope' '$VER' && grep -qF \"'rescope'\" '$WB' && grep -qF 'rescoped' '$LED'"
chk "F cost is not a verdict"                                            "grep -qiF 'Cost is not a verdict' '$VER'"
chk "F deferred rows are uncapped (no MAX_DEFERRED)"                     "! grep -qF 'MAX_DEFERRED = 1' '$ARX/scripts/lib/bundle_io.py'"
chk "F assets do not kill; they become spec constraints"                 "grep -qiF 'does NOT kill the candidate' '$SCR' && ! grep -qF 'asset_dead' '$WB'"
chk "F a failed prior-art query is not an empty result"                  "grep -qiF 'A failed query is not an empty result' '$SCR'"
chk "F asset regression is a warning, not an integrity kill"             "grep -qF '_warn(res, \"asset_regressed\"' '$ARX/scripts/verify_bundle.py'"
chk "F unknown kill_reason is not coerced to fraud"                      "grep -qF '\"unspecified\"' '$LED' && ! grep -qF 'else \"integrity_violation\",' '$LED'"
chk "F S2 pacer is cross-process (file lock, wall clock)"                "grep -qF 'flock' '$ARX/scripts/lib/s2_client.py' && grep -qF '_pace_file' '$ARX/scripts/lib/s2_client.py'"
chk "F HuggingFace listing requests blob sizes"                          "grep -qF 'blobs' '$ARX/scripts/lib/asset_listing.py'"
chk "F verify_bundle configures the S2 client before replaying"          "grep -qF 'config.load_config()' '$ARX/scripts/verify_bundle.py'"
chk "F kill re-adjudication tool exists and never edits the ledger"      "test -f '$ARX/scripts/replay_kills.py' && grep -qiF 'NEVER edits the ledger' '$ARX/scripts/replay_kills.py'"

chk "C generator-consistency gate exists (claim/threshold drift vs ideas file)" "grep -qF 'claim_drift' '$ARX/scripts/verify_bundle.py' && grep -qF -- '--ideas' '$ARX/scripts/verify_bundle.py'"
chk "C threshold-drift + rescope gates exist in V0"   "grep -qF 'threshold_drift' '$ARX/scripts/verify_bundle.py' && grep -qF 'rescope_without_probe' '$ARX/scripts/verify_bundle.py'"
chk "C probe executor exists with the no-network gate + PROBE_VERDICT contract" "test -x '$ARX/bin/probe_run.sh' && grep -qF 'PROBE_VERDICT' '$ARX/bin/probe_run.sh' && grep -qF 'forbidden import' '$ARX/bin/probe_run.sh'"
chk "C asset listing exists with the allowlist + code floor" "test -x '$ARX/bin/asset_listing.sh' && grep -qF 'ALLOWLIST' '$ARX/scripts/lib/asset_listing.py' && grep -qF 'MIN_CODE_BYTES' '$ARX/scripts/lib/asset_listing.py'"
chk "C bundle validating writer refuses missing evidence files" "grep -qF 'not found on disk' '$ARX/scripts/lib/bundle_io.py'"

# ── D — research.js coordination ────────────────────────────────────────────────────────────────────
chk "D phaseSeedVerify is GONE (absorbed, not toggled)" "! grep -qF 'function phaseSeedVerify(' '$SPEC' && ! grep -qF \"case 'seed_verify'\" '$SPEC'"
chk "D applyPickedIdea goes straight to setup_workspace" "grep -qF \"state.stage = 'setup_workspace'                                    // → one-time workspace bootstrap\" '$SPEC'"
chk "D GATE-1 card carries verification + freshness"  "grep -qF 'verification: s.verification' '$SPEC' && grep -qF 'freshness: seedFreshness(s)' '$SPEC'"
chk "D seedFreshness is zero-token + tolerant (never a gate)" "grep -qF 'function seedFreshness(' '$SPEC' && grep -qF -- '--freshness' '$SPEC'"
chk "D parseRefinedSeeds contract documents the Verification Record parse" "grep -qF \"'## Verification Record'\" '$SPEC'"
chk "D HANDOFF folds the Record as BINDING INPUT with mandatory deferred probes" "grep -qF 'VERIFICATION RECORD' '$SPEC' && grep -qF 'MANDATORY: author it as a Phase 0 check' '$SPEC'"
chk "D SEED-VERIFY.md is a stale pointer (rubric preserved in stale/)" "grep -qiF 'RETIRED' '$ROOT/spec/spawn-prompts/SEED-VERIFY.md'"
chk "D research.js still parses"                      "node --check '$SPEC'"

# ── E — kill-path skills + separations ──────────────────────────────────────────────────────────────
chk "E the four kill-path skills exist"               "test -f '$ARX/skills/arxiv-screen/SKILL.md' && test -f '$ARX/skills/arxiv-verify/SKILL.md' && test -f '$ARX/skills/arxiv-recheck/SKILL.md' && test -f '$ARX/skills/arxiv-refute/SKILL.md'"
chk "E the retired skills are gone"                   "! test -d '$ARX/skills/arxiv-idea-judge' && ! test -d '$ARX/skills/arxiv-refine' && ! test -d '$ARX/skills/arxiv-ideate'"
chk "E verifier implements probes from PRE-REGISTERED criteria (never moves thresholds)" "grep -qiF 'never move the threshold' '$ARX/skills/arxiv-verify/SKILL.md' || grep -qiF 'you never move the threshold' '$ARX/skills/arxiv-verify/SKILL.md'"
chk "E verifier may kill, never re-aim"               "grep -qiF 'you may kill; you may never re-aim' '$ARX/skills/arxiv-verify/SKILL.md'"
chk "E recheck transcribes src anchors (fabricated-number defense)" "grep -qiF 'TRANSCRIBE' '$ARX/skills/arxiv-recheck/SKILL.md'"
chk "E refute owns WebSearch; screen has it ONLY as the S2-down fallback" "grep -qE '^allowed-tools:.*WebSearch' '$ARX/skills/arxiv-refute/SKILL.md' && ! grep -qE '^allowed-tools:.*WebSearch' '$ARX/skills/arxiv-recheck/SKILL.md' && ! grep -qE '^allowed-tools:.*WebSearch' '$ARX/skills/arxiv-verify/SKILL.md' && grep -qiF 'FALLBACK when S2 itself is down' '$ARX/skills/arxiv-screen/SKILL.md'"
chk "E a fallback query cannot be laundered as s2_novelty" "grep -qF 'arxiv_web_fallback is only allowed when prior_art.degraded is true' '$ARX/scripts/lib/bundle_io.py'"
chk "E degraded prior-art must name its reason"      "grep -qF '_need_str(pa, \"degraded_reason\", path)' '$ARX/scripts/lib/bundle_io.py'"
chk "E S2 backoff is exponential with jitter"        "grep -qF 'random.uniform(0.0, ceiling)' '$ARX/scripts/lib/s2_client.py' && ! grep -qF 'time.sleep(SLEEP_429_S)' '$ARX/scripts/lib/s2_client.py'"
chk "E backoff honours Retry-After when present"     "grep -qF 'Retry-After' '$ARX/scripts/lib/s2_client.py'"
chk "E every configured S2 key is tried, not just the first" "grep -qF 'def _keys(' '$ARX/scripts/lib/s2_client.py' && grep -qF 'S2_API_KEY_2' '$ARX/scripts/lib/s2_client.py' && grep -qF 'def _send(' '$ARX/scripts/lib/s2_client.py'"
chk "E a refused key (401/403) is abandoned, not retried" "grep -qF 'resp.status_code in (401, 403)' '$ARX/scripts/lib/s2_client.py'"
chk "E web is the LAST rung, after key rotation"      "grep -qiF 'Three channels, cheapest first' '$SCR' && grep -qiF 'every key was' '$SCR'"
chk "E supplement != degraded (S2 working, gap filled)" "grep -qiF 'bundle is NOT degraded' '$SCR'"
chk "E 5xx is retried, not raised (S2 FAQ guidance)" "grep -qF 'def _retryable(' '$ARX/scripts/lib/s2_client.py' && grep -qF 'code == 429 or code >= 500' '$ARX/scripts/lib/s2_client.py'"
chk "E retries ride the pacer (a retry is a request)" "grep -qF '_throttle()                                     # retries are requests too' '$ARX/scripts/lib/s2_client.py'"
chk "E pacing sits under the documented 1 RPS"       "python3 -c \"import yaml,sys; v=yaml.safe_load(open('$ARX/config/config.yaml'))['io']['s2_min_interval_s']; sys.exit(0 if v>=1.0 else 1)\""
chk "E screen owns the similar-merge (merge != kill)" "grep -qiF 'merge is NOT a kill' '$ARX/skills/arxiv-screen/SKILL.md'"
chk "E no-rescue hard principle pinned in the bundle contract" "grep -qiF 'NO successor/rescue channel' '$ARX/skills/arxiv-verify/references/verification-bundle.md'"

echo "----------------------------------------"
echo "t70: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
