#!/usr/bin/env bash
# T27 — PD assets present + resolvable (Doc A §3.1/§6.5, Doc C §5.2 #8). The concern-reference-map is the ONLY
# link between the open-items ledger and skill references; if a concern points at a missing file the goal-builder
# would disclose a dead path. Also pins VERIFY-PROTOCOL.md (the extracted verifier rubric) + the config wiring.
# Run: bash tests/t27_concern_map_presence.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok()  { echo "PASS  $1"; pass=$((pass+1)); }
no()  { echo "FAIL  $1"; fail=$((fail+1)); }

MAP="$ROOT/assets/concern-reference-map.yaml"
VP="$ROOT/spec/spawn-prompts/VERIFY-PROTOCOL.md"
SPEC="$ROOT/spec/research.js"
SKILLS="$ROOT/plugins/paper-polish-ar/skills"
CFG="$ROOT/config/config.yaml"

[ -f "$MAP" ] && ok "concern-reference-map.yaml exists" || no "concern-reference-map.yaml missing"
[ -f "$VP" ]  && ok "VERIFY-PROTOCOL.md exists"          || no "VERIFY-PROTOCOL.md missing"

# Map parses + EVERY reference path (relative to the skills root) resolves to a real file.
MAP="$MAP" SKILLS="$SKILLS" python3 - <<'PY' && ok "every concern reference resolves to a real file" || no "a concern reference does not resolve"
import os, sys, yaml
m = yaml.safe_load(open(os.environ["MAP"])); root = os.environ["SKILLS"]
assert isinstance(m, dict) and m, "map empty/not a dict"
missing = []
for concern, refs in m.items():
    assert isinstance(refs, list) and refs, f"{concern}: not a non-empty list"
    for r in refs:
        if not os.path.isfile(os.path.join(root, r)): missing.append(f"{concern} -> {r}")
if missing:
    print("MISSING:", *missing, sep="\n  "); sys.exit(1)
print("ok: %d concerns, all references resolve" % len(m))
PY

# VERIFY-PROTOCOL.md carries the full rubric + the substitution tokens the slim verifierGoal fills.
miss=0
for v in V1 V2 V3 V4 V5 V6 V7 V8 V9 V10 "CONTRIBUTION SUBSTANCE" "contribution-hollow" "NO DEMOTION" "VERDICT"; do grep -qF "$v" "$VP" || { miss=1; echo "    (VERIFY-PROTOCOL.md missing: $v)"; }; done
[ "$miss" = 0 ] && ok "VERIFY-PROTOCOL.md has V1–V10 (incl. contribution gate) + NO DEMOTION + VERDICT" || no "VERIFY-PROTOCOL.md incomplete"
miss=0
# the two citation-floor tokens retired 2026-08-30 with V7's manuscript-completeness arm (there is no
# manuscript; the bibliography floors are met + audited at the LITERATURE milestone instead).
for t in "<ROUND>" "<WS>" "<REQUIRE_FIGURES>" "<AUDIT_SKILLS>" "<ALLOW_SPAWN>" "<CODE_AUDIT_NO_HARDCODED>"; do grep -qF "$t" "$VP" || { miss=1; echo "    (missing token: $t)"; }; done
[ "$miss" = 0 ] && ok "VERIFY-PROTOCOL.md has all 6 substitution tokens" || no "VERIFY-PROTOCOL.md missing a token"

# concern_map stays a config path; the verifier rubric is NO LONGER config — verifierGoal references it
# DIRECTLY from spec/spawn-prompts/ (one level down from research.js; no config indirection, no assets/).
CFG="$CFG" python3 - <<'PY' && ok "config paths.concern_map wired" || no "config concern_map path missing"
import os, yaml
c = yaml.safe_load(open(os.environ["CFG"]))
assert c["paths"]["concern_map"].endswith("concern-reference-map.yaml")
assert "verify_spec" not in c["paths"], "verify_spec must NOT be a config path (spawn prompts live in spec/spawn-prompts/)"
print("ok")
PY
grep -qF 'spec/spawn-prompts/VERIFY-PROTOCOL.md' "$SPEC" && ok "verifierGoal references VERIFY-PROTOCOL.md directly (spec/spawn-prompts/)" || no "verifierGoal lost its direct VERIFY-PROTOCOL.md reference"

echo "----"; echo "t27_concern_map_presence: $pass passed, $fail failed"; [ "$fail" = 0 ]
