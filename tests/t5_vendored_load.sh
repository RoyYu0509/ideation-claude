#!/usr/bin/env bash
# T5 — vendored-plugin load + config + cfgval + role->model routing + ISOLATION manifests. Runs the
# MECHANICAL checks here; the LIVE check (skills resolve from the vendored -ar copies, NOT the global
# originals) needs a FRESH session in this repo (or /reload-plugins) and is recorded in tests/TESTS.md
# with its expected result. Run: bash tests/t5_vendored_load.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# 1. L0 config.yaml loads
chk "config/config.yaml parses" "python3 -c \"import yaml; yaml.safe_load(open('$ROOT/config/config.yaml'))\""

# 2. cfgval.sh against the vendored arxiv config: real key returns a value; bogus key fails loud (exit 1)
chk "cfgval real key (scout.prefetch_top_k) -> non-MISSING" \
    "v=\$(bash '$ROOT/plugins/arxiv-recommender-ar/bin/cfgval.sh' scout.prefetch_top_k); echo \"\$v\" | grep -qvE 'MISSING' && [ -n \"\$v\" ]"
chk "cfgval bogus key -> <MISSING KEY> + exit 1" \
    "out=\$(bash '$ROOT/plugins/arxiv-recommender-ar/bin/cfgval.sh' scout.nope_nope 2>&1); rc=\$?; echo \"\$out\" | grep -q 'MISSING KEY' && [ \$rc -eq 1 ]"

# 3. role -> model routing is CONFIG-DRIVEN (RC-8): assert every role L0 spawns is defined with a non-empty
#    model id + a `think` field — do NOT hardcode a tier (config is the SSOT). Drift = a MISSING/empty/malformed
#    role, NOT "the tier changed". This is the assertion that would have caught the silent opus->sonnet swap
#    (the old hardcoded-tier check FAILed silently for days; cf. RC-8).
chk "role->model routing: all required roles defined with a non-empty model + think field" "ROOT='$ROOT' python3 -c \"
import os,yaml,sys
m=yaml.safe_load(open(os.path.join(os.environ['ROOT'],'config/config.yaml')))['models']
required=['ideation_orchestrator','review_orchestrator','seed_to_handoff','independent_verifier','experiment_worker','dossier_writer','spec_freezer']
ok=all(r in m and isinstance(m[r].get('model'),str) and m[r]['model'].strip() and ('think' in m[r]) for r in required)
sys.exit(0 if ok else 1)\""

# 4. ISOLATION manifests: vendored plugins renamed to -ar, marketplaces to -ar-local
chk "arxiv vendored plugin name = arxiv-recommender-ar" \
    "python3 -c \"import json;assert json.load(open('$ROOT/plugins/arxiv-recommender-ar/.claude-plugin/plugin.json'))['name']=='arxiv-recommender-ar'\""
chk "paper-polish vendored plugin name = paper-polish-ar" \
    "python3 -c \"import json;assert json.load(open('$ROOT/plugins/paper-polish-ar/.claude-plugin/plugin.json'))['name']=='paper-polish-ar'\""

# 5. settings.json enables all monorepo plugins from the unified marketplace and the global ORIGINALS are NOT
#    active (no collision). The originals must not be ENABLED — whether explicitly disabled OR simply not
#    installed both satisfy the invariant (the global-original marketplaces are no longer installed here, so
#    requiring an explicit `False` entry for a plugin that does not exist is over-strict; `is not True` is the
#    real invariant: the -ar vendored copies win and nothing resolves to a global original).
if [ -f "$ROOT/.claude/settings.json" ]; then
chk "settings.json: globals not enabled + mono plugins enabled + self enabled" "ROOT='$ROOT' python3 -c \"
import os,json,sys
s=json.load(open(os.path.join(os.environ['ROOT'],'.claude/settings.json')))
ep=s['enabledPlugins']; mk=s['extraKnownMarketplaces']
need_true=['auto-research@auto-research','arxiv-recommender-ar@auto-research','paper-polish-ar@auto-research','experiment-lab-ar@auto-research']
need_not_enabled=['arxiv-recommender@arxiv-recommender-local','paper-polish@paper-polish-local']
ok = all(ep.get(k) is True for k in need_true) and all(ep.get(k) is not True for k in need_not_enabled)
ok = ok and ('auto-research' in mk)
sys.exit(0 if ok else 1)\""
fi

echo "----"; echo "t5_vendored_load: $pass passed, $fail failed"; [ "$fail" = 0 ]
