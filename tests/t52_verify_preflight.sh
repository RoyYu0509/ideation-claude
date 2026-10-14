#!/usr/bin/env bash
# T52 — bin/verify_preflight.sh: the B4-25 MECHANICAL PREFLIGHT sensor. It SINKS the five purely-mechanical
# existence/sync/provenance facts (V4 Gate-4a verdict presence / claim-correspondence verdict presence /
# V6 number-sync candidates / V7 figure→plot-script trace / \cite→.bib fabrication) out of the verifier's
# single no-spawn context, writing <ws>/.verify-preflight.json.
# It is a PURE SENSOR: exit 2 (fail loud) ONLY on a usage/script error, never non-zero on a mechanical FAIL.
# Run: bash tests/t52_verify_preflight.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PF="$ROOT/bin/verify_preflight.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

status_of(){ python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(next((c['status'] for c in d['checks'] if c['check']==sys.argv[2]),'MISSING'))" "$1" "$2"; }
beltfail_of(){ python3 -c "import json,sys; print(str(json.load(open(sys.argv[1]))['belt_fail']).lower())" "$1"; }

# a COMPLETE, clean science fixture builder: recorded Gate-4a verdict, a figure that exists + a plot script,
# a \cite that resolves, and paper numbers that all match a source artifact.
build_clean(){
  local ws="$1"; mkdir -p "$ws/paper" "$ws/code"
  printf 'Gate 4a: reproduce-first passed on all seeds.\n' > "$ws/RESEARCH_LOG.md"
  printf '{"acc": 0.95}\n' > "$ws/code/result.json"
  printf 'import matplotlib\nplt.savefig("fig1.pdf")\n' > "$ws/code/plot.py"
  : > "$ws/paper/fig1.pdf"
  printf '@article{smith2020, title={X}, year={2020}}\n' > "$ws/paper/references.bib"
  printf 'We report accuracy 0.95 \\includegraphics{fig1} as shown \\cite{smith2020}.\n' > "$ws/paper/main.tex"
}

# 1) fail-loud usage errors => exit 2
bash "$PF" >/dev/null 2>&1; [ $? -eq 2 ] && ok "missing <workspace> => exit 2" || no "missing ws not refused"
bash "$PF" "$TMP/nope" science >/dev/null 2>&1; [ $? -eq 2 ] && ok "nonexistent workspace => exit 2" || no "bad ws not refused"
WS0="$TMP/w0"; mkdir -p "$WS0"
bash "$PF" "$WS0" bogus >/dev/null 2>&1; [ $? -eq 2 ] && ok "bad <scope> => exit 2" || no "bad scope not refused"

# 2) CLEAN science fixture => every relevant check PASS, sensor exits 0, belt_fail=false
WS1="$TMP/clean"; build_clean "$WS1"
bash "$PF" "$WS1" science >/dev/null 2>&1 && [ -f "$WS1/.verify-preflight.json" ] \
  && ok "clean science run exits 0 and writes .verify-preflight.json" || no "clean run failed or no JSON"
[ "$(status_of "$WS1/.verify-preflight.json" V4-gate4a-verdict-presence)" = PASS ] && ok "V4 verdict-presence PASS on recorded Gate-4a" || no "V4 not PASS"
[ "$(status_of "$WS1/.verify-preflight.json" V7-figure-plot-script-trace)" = PASS ] && ok "V7 figure→plot-script PASS (figure exists + plot script)" || no "V7 not PASS"
[ "$(status_of "$WS1/.verify-preflight.json" cite-bib-fabrication)" = PASS ] && ok "cite→.bib PASS (\\cite resolves)" || no "cite not PASS"
[ "$(beltfail_of "$WS1/.verify-preflight.json")" = false ] && ok "clean fixture => belt_fail=false" || no "clean fixture belted"

# 3) FABRICATED \cite => cite-bib-fabrication FAIL + belt_fail=true (belt-eligible mechanical fact)
WS2="$TMP/badcite"; build_clean "$WS2"
printf 'We report accuracy 0.95 \\includegraphics{fig1} as shown \\cite{ghost2099}.\n' > "$WS2/paper/main.tex"
bash "$PF" "$WS2" science >/dev/null 2>&1
[ "$(status_of "$WS2/.verify-preflight.json" cite-bib-fabrication)" = FAIL ] && ok "fabricated \\cite => cite check FAIL" || no "fabricated cite not FAILed"
[ "$(beltfail_of "$WS2/.verify-preflight.json")" = true ] && ok "fabricated \\cite => belt_fail=true" || no "fabricated cite not belted"

# 4) figure \includegraphics'd but NO plot script under code/ => V7 FAIL + belt_fail=true
WS3="$TMP/nofig"; build_clean "$WS3"; rm -f "$WS3/code/plot.py"
bash "$PF" "$WS3" science >/dev/null 2>&1
[ "$(status_of "$WS3/.verify-preflight.json" V7-figure-plot-script-trace)" = FAIL ] && ok "figure with no plot script => V7 FAIL" || no "untraced figure not FAILed"
[ "$(beltfail_of "$WS3/.verify-preflight.json")" = true ] && ok "untraced figure => belt_fail=true" || no "untraced figure not belted"

# 5) non-empty RESEARCH_LOG with NO Gate-4a verdict token => V4 FAIL (absent-but-nonempty distinct from NA)
WS4="$TMP/nogate"; build_clean "$WS4"
printf 'Ran some experiments today. Numbers look fine.\n' > "$WS4/RESEARCH_LOG.md"
bash "$PF" "$WS4" science >/dev/null 2>&1
[ "$(status_of "$WS4/.verify-preflight.json" V4-gate4a-verdict-presence)" = FAIL ] && ok "log with no recorded Gate-4a verdict => V4 FAIL" || no "missing gate-4a verdict not FAILed"

# 6) FOCUSED scope => SCIENCE-only checks (V7, cite) are NA (belt-eligible but NA never belts); V4/V6 still live
WS5="$TMP/focused"; build_clean "$WS5"
bash "$PF" "$WS5" focused >/dev/null 2>&1
[ "$(status_of "$WS5/.verify-preflight.json" V7-figure-plot-script-trace)" = NA ] && ok "focused scope => V7 NA" || no "focused V7 not NA"
[ "$(status_of "$WS5/.verify-preflight.json" cite-bib-fabrication)" = NA ] && ok "focused scope => cite NA" || no "focused cite not NA"
[ "$(status_of "$WS5/.verify-preflight.json" V4-gate4a-verdict-presence)" = PASS ] && ok "focused scope => V4 still runs (PASS)" || no "focused V4 not run"
[ "$(beltfail_of "$WS5/.verify-preflight.json")" = false ] && ok "focused NA checks never belt" || no "focused NA belted"

# 7) require_figures=false (science) => V7 NA even with a figure present. Point CLAUDE_PLUGIN_ROOT at a temp root
#    whose config sets the flag false. Needs pyyaml (the script defaults True without it) — SKIP LOUDLY if absent.
if python3 -c "import yaml" 2>/dev/null; then
  FR="$TMP/root"; mkdir -p "$FR/config"
  printf 'drafting:\n  require_figures: false\n' > "$FR/config/config.yaml"
  WS6="$TMP/nofigflag"; build_clean "$WS6"
  CLAUDE_PLUGIN_ROOT="$FR" bash "$PF" "$WS6" science >/dev/null 2>&1
  [ "$(status_of "$WS6/.verify-preflight.json" V7-figure-plot-script-trace)" = NA ] && ok "require_figures=false => V7 NA (figureless paper is legal)" || no "require_figures=false V7 not NA"
else
  echo "SKIP  require_figures=false case (python3 yaml not installed)"
fi

# 8) claim-correspondence (c) verdict presence — the split gate's mechanical PRESENCE half (both scopes)
#    clean fixture has no EXPERIMENTS/ => NA; a result.md with both halves => PASS; missing/half => FAIL+belt
[ "$(status_of "$WS1/.verify-preflight.json" claim-correspondence-verdict-presence)" = NA ] \
  && ok "no EXPERIMENTS/*/result.md => claim-correspondence NA" || no "claim-correspondence not NA without result.md"
WS7="$TMP/cc"; build_clean "$WS7"; mkdir -p "$WS7/EXPERIMENTS/E1"
printf 'Claim-correspondence (c) verdict: structural pass (author time); behavioral pass (read off this run).\n' \
  > "$WS7/EXPERIMENTS/E1/result.md"
bash "$PF" "$WS7" focused >/dev/null 2>&1
[ "$(status_of "$WS7/.verify-preflight.json" claim-correspondence-verdict-presence)" = PASS ] \
  && ok "result.md with structural+behavioral (c) verdict => PASS" || no "recorded (c) verdict not PASS"
printf 'Ran fine. Numbers in raw/.\n' > "$WS7/EXPERIMENTS/E1/result.md"
bash "$PF" "$WS7" focused >/dev/null 2>&1
[ "$(status_of "$WS7/.verify-preflight.json" claim-correspondence-verdict-presence)" = FAIL ] \
  && ok "result.md with no (c) verdict => FAIL" || no "missing (c) verdict not FAILed"
[ "$(beltfail_of "$WS7/.verify-preflight.json")" = true ] && ok "missing (c) verdict => belt_fail=true" || no "missing (c) verdict not belted"
printf 'Claim-correspondence verdict: structural pass.\n' > "$WS7/EXPERIMENTS/E1/result.md"
bash "$PF" "$WS7" focused >/dev/null 2>&1
[ "$(status_of "$WS7/.verify-preflight.json" claim-correspondence-verdict-presence)" = FAIL ] \
  && ok "(c) verdict missing its behavioral half => FAIL" || no "half (c) verdict not FAILed"

# 9) V6 retarget — in the loop (no paper/) the number-sync target is FINDINGS-DOSSIER.md,
#    sourced against AUDITED-VALUES.json too; belt stays false (advisory candidates)
WS8="$TMP/dossier"; mkdir -p "$WS8"
printf 'Gate 4a: reproduce-first passed.\n' > "$WS8/RESEARCH_LOG.md"
printf 'Coverage is 0.90 on the full population; error 0.123 on HORM-T1x.\n' > "$WS8/FINDINGS-DOSSIER.md"
printf '{"coverage_full": 0.90}\n' > "$WS8/AUDITED-VALUES.json"
bash "$PF" "$WS8" focused >/dev/null 2>&1
[ "$(status_of "$WS8/.verify-preflight.json" V6-number-sync-candidates)" = FAIL ] \
  && ok "dossier decimal with no source (0.123) => V6 FAIL candidates" || no "unsourced dossier decimal not surfaced"
[ "$(beltfail_of "$WS8/.verify-preflight.json")" = false ] && ok "V6 dossier candidates stay advisory (never belt)" || no "V6 dossier belted"
printf '{"coverage_full": 0.90, "err_horm": 0.123}\n' > "$WS8/AUDITED-VALUES.json"
bash "$PF" "$WS8" focused >/dev/null 2>&1
[ "$(status_of "$WS8/.verify-preflight.json" V6-number-sync-candidates)" = PASS ] \
  && ok "every dossier decimal sourced (incl AUDITED-VALUES.json) => V6 PASS" || no "sourced dossier decimals not PASS"
[ "$(status_of "$WS1/.verify-preflight.json" V6-number-sync-candidates)" = PASS ] \
  && ok "science scope with paper .tex keeps the paper target (no regression)" || no "paper-target V6 regressed"

# 10) md↔bin contract sync — VERIFY-PROTOCOL.md must register the new mechanical fact + the V8 (vi) judgement half
grep -q 'claim-correspondence' "$ROOT/spec/spawn-prompts/VERIFY-PROTOCOL.md" \
  && ok "VERIFY-PROTOCOL.md registers the claim-correspondence preflight fact" || no "VERIFY-PROTOCOL.md missing claim-correspondence"
grep -q 'claim-correspondence-verdict-presence' "$PF" \
  && ok "verify_preflight.sh carries the claim-correspondence-verdict-presence check" || no "preflight missing the new check"
grep -q 'FINDINGS-DOSSIER.md' "$ROOT/spec/spawn-prompts/VERIFY-PROTOCOL.md" \
  && ok "VERIFY-PROTOCOL.md documents the V6 dossier target" || no "VERIFY-PROTOCOL.md missing V6 dossier target"

echo "----"; echo "t52_verify_preflight: $pass passed, $fail failed"; [ "$fail" = 0 ]
