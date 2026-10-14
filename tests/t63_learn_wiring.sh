#!/usr/bin/env bash
# t63 — /learn static wiring. The spec is LLM-read, so a renamed rubric/config key fails at RUNTIME
# unless a test pins the seams. Proves: (1) every rubric spec/learn.js references exists on disk (and
# vice versa: every LEARN-*.md is referenced by learn.js or another rubric); (2) config/config.yaml's
# learning block carries every key learn.js needs; (3) commands/learn.md's MISS-loop covers every
# load-bearing file it names AND all rubrics; (4) the key-config learning panel section applies cleanly
# (--check exits 0 = no MISSING PATH drift); (5) rubric token headers match the tokens learn.js injects.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }
LJS="$ROOT/spec/learn.js"; CMD="$ROOT/commands/learn.md"; SP="$ROOT/spec/spawn-prompts"

# === Case 1: every LEARN-*.md referenced from learn.js exists; every LEARN-*.md on disk is reachable ===
REFS="$(grep -oE 'LEARN-[A-Z-]+\.md' "$LJS" | sort -u)"
missing=""
for f in $REFS; do [ -f "$SP/$f" ] || missing="$missing $f"; done
orphan=""
for f in "$SP"/LEARN-*.md; do
  b="$(basename "$f")"
  grep -q "$b" "$LJS" "$SP"/LEARN-*.md 2>/dev/null | true
  if ! grep -qh "$b" "$LJS" $(ls "$SP"/LEARN-*.md | grep -v "$b") 2>/dev/null; then orphan="$orphan $b"; fi
done
if [ -z "$missing" ] && [ -z "$orphan" ]; then ok "rubric files <-> learn.js references bijective"
else no "rubric wiring (missing:$missing orphan:$orphan)"; fi

# === Case 2: config learning block carries every key learn.js reads ===
if python3 - "$ROOT" <<'PY'
import sys, yaml
root = sys.argv[1]
cfg = yaml.safe_load(open(root + "/config/config.yaml"))
L = cfg["learning"]
for k in ("max_component_reviewers", "verify_themes_max", "proposals_max",
          "findings_index_max_lines", "dossier_brief_max_lines", "trace_depth", "models"):
    assert k in L, "learning.%s missing" % k
for r in ("evidence_packer", "venue_cold_reader", "component_reviewer", "crosscut_reviewer", "adversarial_verifier", "synthesizer"):
    assert r in L["models"] and "model" in L["models"][r], "learning.models.%s missing/malformed" % r
PY
then ok "config learning block complete (all keys learn.js needs)"; else no "config learning block"; fi

# === Case 3: learn.md MISS-loop covers all rubrics + the bins/assets learn.js calls ===
missing3=""
for f in LEARN-CHARTER.md LEARN-EVIDENCE-PACK.md LEARN-VENUE-COLDREAD.md LEARN-COMPONENT-REVIEW.md \
         LEARN-CROSSCUT-SCIENCE.md LEARN-CROSSCUT-ECONOMICS.md LEARN-CROSSCUT-ENACTMENT.md \
         LEARN-CROSSCUT-QUALITY.md LEARN-ADVERSARIAL-VERIFY.md LEARN-SYNTHESIS.md; do
  grep -q "spec/spawn-prompts/$f" "$CMD" || missing3="$missing3 $f"
done
for f in bin/learn_resolve.sh bin/learn_manifest.py bin/learn_hypotheses.py bin/learn_quality_ledger.py \
         bin/run_report.py bin/archive_decision.sh bin/validate_envelope.sh assets/learn-dossier-template.md \
         assets/learn-hypotheses-schema.json assets/learn-quality-ledger-schema.json \
         assets/decision-file-template.md spec/l1-envelope-schema.json; do
  grep -q "$f" "$CMD" || missing3="$missing3 $f"
done
# and everything the MISS-loop names must exist on disk (skip placeholder fragments like LEARN-<X>.md,
# whose '<' truncates the regex match)
for f in $(grep -oE '(spec|bin|assets)/[A-Za-z0-9/_.\-]+' "$CMD" | sort -u); do
  case "$f" in *-|*.) continue ;; esac
  [ -e "$ROOT/$f" ] || missing3="$missing3 (disk:$f)"
done
if [ -z "$missing3" ]; then ok "learn.md preconditions cover rubrics+bins+assets, all present on disk"
else no "learn.md preconditions ($missing3)"; fi

# === Case 4: key-config learning panel applies cleanly (no MISSING PATH drift) ===
if bash "$ROOT/bin/apply_key_config.sh" --check >/dev/null 2>&1; then
  ok "apply_key_config --check exits 0 (learning mappings resolve)"
else no "apply_key_config --check (drift in learning mappings?)"; fi

# === Case 5: tokens learn.js injects appear in each rubric's token header ===
if python3 - "$ROOT" <<'PY'
import sys, re, os
root = sys.argv[1]
ljs = open(root + "/spec/learn.js").read()
pairs = {
 "LEARN-EVIDENCE-PACK.md":    ["<LEARN_DIR>", "<MANIFEST>", "<SOURCE_REPO>", "<RUN_DECISIONS>", "<HYPOTHESES>", "<QUALITY_LEDGER>", "<OUT>"],
 "LEARN-VENUE-COLDREAD.md":   ["<VENUE>", "<VENUE_PACK_JSON>", "<PAPER_DIR>", "<PANEL_VERDICTS>", "<TERMINAL_JSON>", "<OUT>", "<OUT_JSON>"],
 "LEARN-COMPONENT-REVIEW.md": ["<GROUP>", "<MANIFEST>", "<EVIDENCE_PACK>", "<WS>", "<TRACE_DEPTH>", "<VENUE_COLDREAD>", "<OUT>", "<INDEX>"],
 "LEARN-CROSSCUT-SCIENCE.md": ["<ROLLUP>", "<TRACE_DIR>", "<RUN_REPORT>", "<OUT>", "<INDEX>"],
 "LEARN-CROSSCUT-QUALITY.md": ["<VENUE_COLDREAD>", "<VENUE_COLDREAD_JSON>", "<QUALITY_LEDGER>", "<OUT>", "<INDEX>"],
 "LEARN-ADVERSARIAL-VERIFY.md": ["<THEME>", "<CLAIMS>", "<REVIEW_FILES>", "<VENUE_COLDREAD>", "<VENUE_COLDREAD_JSON>", "<OUT>"],
 "LEARN-SYNTHESIS.md":        ["<RATIFY_QUEUE>", "<HYP_VERDICTS>", "<TEMPLATE>", "<DOSSIER_HOME>", "<BRIEF>", "<PROPOSALS_MAX>", "<VENUE_COLDREAD_JSON>", "<QUALITY_LEDGER>", "<QUALITY_RECORD>"],
}
for fname, toks in pairs.items():
    body = open(os.path.join(root, "spec/spawn-prompts", fname)).read()
    for t in toks:
        assert t in body, "%s missing token %s" % (fname, t)
        assert t in ljs or t == "<GROUP>" or t == "<THEME>" or t == "<CLAIMS>", "learn.js never injects %s" % t
PY
then ok "token headers <-> learn.js injections consistent"; else no "token consistency"; fi

echo "----"; echo "t63_learn_wiring: $pass passed, $fail failed"; [ "$fail" = 0 ]
