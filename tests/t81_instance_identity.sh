#!/usr/bin/env bash
# t81_instance_identity.sh — a new folder's identity and paper list are the OWNER's calls (2026-09-13).
#   A — gateAnsweredBy routes kind 'identity' to the owner unconditionally (like GATE-1's seed_select)
#   B — phaseIdeation opens the researcher-identity card when the folder has no researcher.json (the monorepo
#       itself and ideation-only mode skip it) and routes a 'paper-list' escalation to an owner card
#   C — ingest writes researcher.json via set_researcher.py (Scholar URL + names) or the shared-default marker,
#       relays paper-list answers through set_paper_decisions.py, and re-presents instead of guessing
#   D — IDEATION-L0 returns the 0b gate as a 'paper-list' escalation; arxiv-scout Phase 0a reuses a pending
#       list; ar-init.sh exposes --scholar
#   E — set_paper_decisions.py behaviour: an ambiguous mark writes nothing; marks + --rest settle every row
# Run: bash tests/t81_instance_identity.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"; L0="$ROOT/spec/spawn-prompts/IDEATION-L0.md"; ARX="$ROOT/plugins/arxiv-recommender-ar"
pass=0; fail=0
chk() { if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

chk "A identity kind is always the owner's"        "grep -qF \"if (kind === 'identity') return 'owner'\" '$SPEC'"
chk "B identity card when no researcher.json"      "grep -qF \"gate(state, 'researcher-identity', 'identity'\" '$SPEC'"
chk "B the monorepo and ideation-only skip it"     "grep -qF '/spec/research.js\`)' '$SPEC' && grep -qF '/.ar-ideation-only\`)' '$SPEC'"
chk "B paper-list escalation → owner card"         "grep -qF \"gate(state, 'ideation-paperlist', 'identity'\" '$SPEC'"
chk "C ingest pins via set_researcher --scholar"   "grep -qF 'set_researcher.py\" --store' '$SPEC' && grep -qF -- '--scholar \${JSON.stringify(url)}' '$SPEC'"
chk "C shared-default marker"                      "grep -qF 'use_shared_default: true' '$SPEC'"
chk "C paper list relayed by set_paper_decisions"  "grep -qF 'scripts/set_paper_decisions.py' '$SPEC'"
chk "C a bad answer re-presents the card"          "grep -qF 'return identityGate(state, ' '$SPEC' && grep -qF 'return paperListGate(state, ' '$SPEC'"
chk "D IDEATION-L0 returns the paper-list gate"    "grep -qF \"escalation with id 'paper-list'\" '$L0'"
chk "D Phase 0a reuses a pending list"             "grep -qF 'const pendingList' '$ARX/workflows/arxiv-scout.js'"
chk "D ar-init exposes --scholar"                  "grep -qF -- '--scholar)' '$ROOT/bin/ar-init.sh'"

# E — behaviour (the plugin venv: the script imports build_profile_papers)
PY="$ARX/.venv/bin/python"; [ -x "$PY" ] || PY=python3
T="$(mktemp -d)"
cat > "$T/c.json" <<'JSON'
{"name": "Ada", "source": {"kind": "url", "url": "u"}, "fetched_at_utc": "2026-09-13T00:00:00", "name_forms": [],
 "papers": [{"key": "a1", "title": "Random feature methods", "decision": null},
            {"key": "a2", "title": "Random walks", "decision": null},
            {"key": "a3", "title": "Protein QA", "decision": null}]}
JSON
AR_DATA_ROOT="$T" "$PY" "$ARX/scripts/set_paper_decisions.py" --candidates "$T/c.json" --mark 'random=not' --rest self >/dev/null 2>&1; rc=$?
chk "E ambiguous mark → exit 2, nothing written"  "[ $rc = 2 ] && grep -qF '\"decision\": null' '$T/c.json'"
AR_DATA_ROOT="$T" "$PY" "$ARX/scripts/set_paper_decisions.py" --candidates "$T/c.json" --mark 'Protein QA=peripheral' --mark 'a2=not' --rest self >/dev/null 2>&1; rc=$?
chk "E marks + --rest settle every row"           "[ $rc = 0 ] && '$PY' -c \"import json,sys; d=json.load(open('$T/c.json')); sys.exit(0 if [p['decision'] for p in d['papers']] == ['self','not','peripheral'] else 1)\""
rm -rf "$T"

echo "t81: $pass passed, $fail failed"
[ "$fail" = 0 ]
