#!/usr/bin/env bash
# T54 — plugins/paper-polish-ar/hooks/git_sweep_guard.py: the Bash PreToolUse guard that replaces the
# repeated "never git add -A" prose in the polish/figure specs (B4-18). While a polish/figure run is armed
# (.polish/fidelity-manifest.json mode=polish|figure) it denies the sweep forms (add -A/-a/--all,
# commit -a/-am/--all); L0's legitimate workspace-scoped `git add -A` in review/consolidate/experiment
# modes — and everything with no manifest — passes straight through. Any internal error fails open.
# Run: bash tests/t54_git_sweep_guard.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARD="$ROOT/plugins/paper-polish-ar/hooks/git_sweep_guard.py"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
arm(){ mkdir -p "$TMP/.polish"; printf '{"mode":"%s"}' "$1" > "$TMP/.polish/fidelity-manifest.json"; }
disarm(){ rm -f "$TMP/.polish/fidelity-manifest.json"; }
run_p(){ CLAUDE_PROJECT_DIR="$TMP" python3 "$GUARD" 2>/dev/null; }
payload(){ printf '{"tool_name":"Bash","tool_input":{"command":"%s"}}' "$1"; }

# 1) no manifest -> allow even a sweep form (no active run = no-op)
disarm
out="$(payload 'git add -A' | run_p)"; rc=$?
[ -z "$out" ] && [ $rc -eq 0 ] && ok "no manifest => allow git add -A" || no "no-manifest not a no-op"

# 2) polish mode: DENY the sweep forms
arm polish
payload 'git -C /x/paper add -A' | run_p | grep -q '"permissionDecision": "deny"' \
  && ok "polish: DENY git -C <dir> add -A" || no "polish add -A not denied"
payload 'git add --all' | run_p | grep -q '"permissionDecision": "deny"' \
  && ok "polish: DENY git add --all" || no "polish add --all not denied"
payload 'git commit -am msg' | run_p | grep -q '"permissionDecision": "deny"' \
  && ok "polish: DENY git commit -am" || no "polish commit -am not denied"

# 3) polish mode: ALLOW the reviser's legitimate scoped forms
out="$(payload 'git -C /x/paper add -- section.tex' | run_p)"
[ -z "$out" ] && ok "polish: ALLOW git add -- <file>" || no "scoped add wrongly denied"
out="$(payload 'git commit --allow-empty -m base' | run_p)"
[ -z "$out" ] && ok "polish: ALLOW commit --allow-empty -m" || no "allow-empty commit wrongly denied"
out="$(payload 'git commit -m \"fix -a flag docs\"' | run_p)"
[ -z "$out" ] && ok "polish: ALLOW -a inside a commit MESSAGE" || no "-a in message wrongly denied"

# 4) figure mode is guarded too
arm figure
payload 'git add -a' | run_p | grep -q '"permissionDecision": "deny"' \
  && ok "figure: DENY git add -a" || no "figure add -a not denied"

# 5) review mode: NO-OP (L0's isolated-workspace add -A is legitimate — blocking would wedge the pipeline)
arm review
out="$(payload 'git -C /x/ws add -A' | run_p)"; rc=$?
[ -z "$out" ] && [ $rc -eq 0 ] && ok "review mode => allow (L0 workspace sweep is legitimate)" || no "review mode wrongly guarded"

# 6) non-Bash tool + unparseable stdin -> allow (fail-open)
arm polish
out="$(printf '{"tool_name":"Write","tool_input":{"file_path":"x"}}' | run_p)"
[ -z "$out" ] && ok "non-Bash tool => allow" || no "non-Bash tool wrongly gated"
out="$(echo 'not json' | run_p)"; rc=$?
[ -z "$out" ] && [ $rc -eq 0 ] && ok "unparseable stdin => fail-open allow" || no "unparseable stdin not fail-open"

# 7) registered in the plugin's hooks.json under a Bash matcher
grep -q "git_sweep_guard.py" "$ROOT/plugins/paper-polish-ar/hooks/hooks.json" \
  && ok "git_sweep_guard.py registered in plugin hooks.json" || no "not registered in plugin hooks.json"

# 8) dossier-12 D2 widening — the V2 bypass/coverage matrix (token-level matcher).
#    DENY: flag insertion, `.`/`..`, -u/--update, trailing-slash dirs, `--`-laundered sweeps,
#    trailing/clustered commit -a, compound commands. ALLOW: named files, message strings, -F,
#    --all on a non-add/commit subcommand, add of a weird -A-prefixed FILENAME.
arm polish
while IFS= read -r c; do
  [ -n "$c" ] || continue
  payload "$c" | run_p | grep -q '"permissionDecision": "deny"' \
    && ok "D2 DENY: $c" || no "D2 sweep NOT denied: $c"
done <<'CASES'
git add -v -A
git add -vA
git add .
git -C /x add .
git add -u
git add --update
git add src/
git add -- .
git add -- src/
git commit -m msg -a
git commit -avm msg
git commit --all -m x
git commit -m x --include f
cd /x && git add -A && git commit -m x
echo ok; git add .
CASES
while IFS= read -r c; do
  [ -n "$c" ] || continue
  out="$(payload "$c" | run_p)"
  [ -z "$out" ] && ok "D2 ALLOW: $c" || no "D2 legit form wrongly denied: $c"
done <<'CASES'
git add -- fig1.py fig2.py
git add section.tex
git add -p -- section.tex
git commit -F notes.txt
git log --all
git add -A-suffix-file
CASES

echo "----"; echo "t54_git_sweep_guard: $pass passed, $fail failed"; [ "$fail" = 0 ]
