#!/usr/bin/env bash
# t8 — bin/verify_panel.sh proof-of-work gate (RC-2): a narrated review with no real panel must FAIL.
# This is the regression for the P2/P3 failure (review never really ran, yet shipped). Run standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
chk(){ if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# fixture: a REAL panel ran — round file with 3 distinct personas + AC, and a report with an Overall-risk line
ok="$TMP/ok"; mkdir -p "$ok/paper"
printf '{"macro":1,"round":1,"panel":[{"persona":"R1","recommendation":"major_revision"},{"persona":"R2","recommendation":"reject"},{"persona":"R3","recommendation":"minor_revision"}],"ac":{"overall_risk":"major_revision"}}\n' > "$ok/paper/review-verdicts.md"
printf '**Overall risk:** major_revision\n\n- punch-list item\n' > "$ok/paper/review-report.md"
chk "real panel (3 personas + ac + report) -> exit 0" "bash '$ROOT/bin/verify_panel.sh' '$ok' 1 3 >/dev/null 2>&1"

# fixture: P2-style — only a narrated report, NO per-round panel files
narr="$TMP/narrated"; mkdir -p "$narr/paper"
printf '**Overall risk:** minor_revision\n' > "$narr/paper/review-report.md"
chk "narrated review, no round files -> exit 2 (RC-2 caught)" "! bash '$ROOT/bin/verify_panel.sh' '$narr' 1 3 >/dev/null 2>&1"

# fixture: a round file but only 2 personas (panel too small to be a real panel)
small="$TMP/small"; mkdir -p "$small/paper"
printf '{"macro":1,"round":1,"panel":[{"persona":"R1"},{"persona":"R2"}],"ac":{"overall_risk":"reject"}}\n' > "$small/paper/review-verdicts.md"
printf '**Overall risk:** reject\n' > "$small/paper/review-report.md"
chk "panel with only 2 personas -> exit 2" "! bash '$ROOT/bin/verify_panel.sh' '$small' 1 3 >/dev/null 2>&1"

# ── round freshness (dossier-12 D3): a STALE round's artifact must not prove THIS round ─────────
stale="$TMP/stale"; mkdir -p "$stale/paper"
printf '{"round":1,"panel":[{"persona":"R1","recommendation":"accept"},{"persona":"R2","recommendation":"accept"}],"ac":{"overall_risk":"accept"}}\n' > "$stale/paper/review-verdicts.md"
printf '**Overall risk:** accept\n' > "$stale/paper/review-report.md"
chk "round=1 artifact verified as round 2 -> exit 2 (stale)" "! bash '$ROOT/bin/verify_panel.sh' '$stale' 2 >/dev/null 2>&1"
chk "same artifact verified as round 1 -> exit 0 (fresh)" "bash '$ROOT/bin/verify_panel.sh' '$stale' 1 >/dev/null 2>&1"
garb="$TMP/garbled"; mkdir -p "$garb/paper"
printf '{"round":"not-a-number","panel":[{"persona":"R1"},{"persona":"R2"}],"ac":{"overall_risk":"accept"}}\n' > "$garb/paper/review-verdicts.md"
printf '**Overall risk:** accept\n' > "$garb/paper/review-report.md"
chk "present-but-garbled round field -> exit 2 (fail-closed)" "! bash '$ROOT/bin/verify_panel.sh' '$garb' 1 >/dev/null 2>&1"
noround="$TMP/noround"; mkdir -p "$noround/paper"
printf '{"panel":[{"persona":"R1","recommendation":"accept"},{"persona":"R2","recommendation":"accept"}],"ac":{"overall_risk":"accept"}}\n' > "$noround/paper/review-verdicts.md"
printf '**Overall risk:** accept\n' > "$noround/paper/review-report.md"
chk "missing round field -> exit 0 (pre-D3 artifacts stay valid)" "bash '$ROOT/bin/verify_panel.sh' '$noround' 3 >/dev/null 2>&1"

# ── acFinal/overall_risk top-level aliases are RETIRED (G6): ac is the only synthesis key ───────
alias_ac="$TMP/aliasac"; mkdir -p "$alias_ac/paper"
printf '{"round":1,"panel":[{"persona":"R1"},{"persona":"R2"}],"acFinal":{"overall_risk":"accept"}}\n' > "$alias_ac/paper/review-verdicts.md"
printf '**Overall risk:** accept\n' > "$alias_ac/paper/review-report.md"
chk "acFinal alias (no ac key) -> exit 2 (alias retired)" "! bash '$ROOT/bin/verify_panel.sh' '$alias_ac' 1 >/dev/null 2>&1"

# ── default floor (no 3rd arg) = 2: the protocol INDEPENDENCE FLOOR, baked into the script ────────
two="$TMP/twodefault"; mkdir -p "$two/paper"
printf '{"round":1,"panel":[{"persona":"R1","recommendation":"major_revision"},{"persona":"R2","recommendation":"reject"}],"ac":{"overall_risk":"major_revision"}}\n' > "$two/paper/review-verdicts.md"
printf '**Overall risk:** major_revision\n' > "$two/paper/review-report.md"
chk "default floor: 2 personas, no explicit min -> exit 0" "bash '$ROOT/bin/verify_panel.sh' '$two' 1 >/dev/null 2>&1"

one="$TMP/onedefault"; mkdir -p "$one/paper"
printf '{"round":1,"panel":[{"persona":"R1","recommendation":"reject"}],"ac":{"overall_risk":"reject"}}\n' > "$one/paper/review-verdicts.md"
printf '**Overall risk:** reject\n' > "$one/paper/review-report.md"
chk "default floor: 1 persona, no explicit min -> exit 2" "! bash '$ROOT/bin/verify_panel.sh' '$one' 1 >/dev/null 2>&1"

# fixture: panel ok but NO review-report.md
norep="$TMP/norep"; mkdir -p "$norep/paper"
cp "$ok/paper/review-verdicts.md" "$norep/paper/review-verdicts.md"
chk "panel ok but no review-report.md -> exit 2" "! bash '$ROOT/bin/verify_panel.sh' '$norep' 1 3 >/dev/null 2>&1"

# missing workspace
chk "missing workspace -> exit 2" "! bash '$ROOT/bin/verify_panel.sh' '$TMP/nope' 1 3 >/dev/null 2>&1"

# ── RC-2b grounding floor (proof-of-READ) ──────────────────────────────────────────────────────────
# fixture: 3 personas + AC, but reviewers raise major findings anchored to NOTHING (quote/location null)
#          — the Reviewer-3 0-tool-use hallucination signature. Must FAIL even though proof-of-work passes.
ungr="$TMP/ungrounded"; mkdir -p "$ungr/paper"
printf '%s\n' '{"round":1,"panel":[{"persona":"R1","findings":[{"axis":"results","severity":"major","problem":"baseline weak","quote":null,"location":null}]},{"persona":"R2","findings":[{"axis":"logic","severity":"reject","problem":"claim unsupported","quote":null,"location":null}]},{"persona":"R3","findings":[{"axis":"novelty","severity":"major","problem":"incremental","quote":null,"location":null}]}],"ac":{"overall_risk":"reject"}}' > "$ungr/paper/review-verdicts.md"
printf '**Overall risk:** reject\n' > "$ungr/paper/review-report.md"
chk "ungrounded major findings (no quotes) -> exit 2 (RC-2b caught)" "! bash '$ROOT/bin/verify_panel.sh' '$ungr' 1 3 >/dev/null 2>&1"

# fixture: same panel but each reviewer anchors >=1 finding with a verbatim quote -> grounded -> exit 0
grd="$TMP/grounded"; mkdir -p "$grd/paper"
printf '%s\n' '{"round":1,"panel":[{"persona":"R1","findings":[{"axis":"results","severity":"major","problem":"baseline weak","quote":"we compare against a single baseline","location":"Sec 4, results.tex"}]},{"persona":"R2","findings":[{"axis":"logic","severity":"reject","problem":"claim unsupported","quote":"the operator is linear","location":"Sec 3, methods.tex"}]},{"persona":"R3","findings":[{"axis":"novelty","severity":"major","problem":"incremental","quote":"prior work already showed","location":"Sec 2, intro.tex"}]}],"ac":{"overall_risk":"reject"}}' > "$grd/paper/review-verdicts.md"
printf '**Overall risk:** reject\n' > "$grd/paper/review-report.md"
chk "grounded major findings (verbatim quotes) -> exit 0" "bash '$ROOT/bin/verify_panel.sh' '$grd' 1 3 >/dev/null 2>&1"

# fixture: reviewers raise ONLY minor findings with no quotes -> low-stakes, exempt from the floor -> exit 0
minor="$TMP/minoronly"; mkdir -p "$minor/paper"
printf '%s\n' '{"round":1,"panel":[{"persona":"R1","findings":[{"axis":"clarity","severity":"minor","problem":"typo","quote":null,"location":null}]},{"persona":"R2","findings":[{"axis":"style","severity":"minor","problem":"wording","quote":null,"location":null}]},{"persona":"R3","findings":[{"axis":"format","severity":"minor","problem":"caption","quote":null,"location":null}]}],"ac":{"overall_risk":"minor_revision"}}' > "$minor/paper/review-verdicts.md"
printf '**Overall risk:** minor_revision\n' > "$minor/paper/review-report.md"
chk "only minor findings, no quotes -> exit 0 (exempt from grounding floor)" "bash '$ROOT/bin/verify_panel.sh' '$minor' 1 3 >/dev/null 2>&1"

# fixture: one reviewer grounded, one NOT -> the ungrounded one still fails the round -> exit 2
mixed="$TMP/mixed"; mkdir -p "$mixed/paper"
printf '%s\n' '{"round":1,"panel":[{"persona":"R1","findings":[{"axis":"results","severity":"major","problem":"weak","quote":"single baseline only","location":"Sec 4"}]},{"persona":"R2","findings":[{"axis":"logic","severity":"reject","problem":"unsupported","quote":null,"location":null}]},{"persona":"R3","findings":[{"axis":"novelty","severity":"minor","problem":"minor","quote":null,"location":null}]}],"ac":{"overall_risk":"reject"}}' > "$mixed/paper/review-verdicts.md"
printf '**Overall risk:** reject\n' > "$mixed/paper/review-report.md"
chk "one reviewer ungrounded among grounded peers -> exit 2" "! bash '$ROOT/bin/verify_panel.sh' '$mixed' 1 3 >/dev/null 2>&1"

echo "----"; echo "t8_verify_panel: $pass passed, $fail failed"; [ "$fail" = 0 ]
