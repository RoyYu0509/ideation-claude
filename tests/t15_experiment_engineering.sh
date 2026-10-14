#!/usr/bin/env bash
# t15 — the experiment-engineering skill wiring. Proves the B1 experiment_worker now gets hardware-aware,
# BOTTLENECK-FIRST engineering guidance: config exposes the skill (+OOM headroom knob), research.js reads it,
# injects its bare name into the experiment_worker goal AND rewrote the blanket no-smoke into the
# probe-vs-scaled-down split; the SKILL.md exists with the !`...` hardware-probe injection + the
# probe/scaled-down section + the four progressive-disclosure reference files; and the probe commands actually
# run on THIS machine. Standalone (no spawn). BSD-grep safe (literal brackets, no \s).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }

CFG="$ROOT/config/config.yaml"
JS="$ROOT/spec/research.js"
ESPEC="$ROOT/plugins/experiment-lab-ar/spec/experiment-protocol.md"   # B1 experiment+drafting goal text now lives here (extracted from research.js)
SK="$ROOT/skills/experiment-engineering/SKILL.md"
REF="$ROOT/skills/experiment-engineering/reference"

# === Case 1: config exposes the engineering skill (oom_headroom_frac was DELETED 2026-07-06 — a dead,
#     zero-reader knob; the OOM discipline lives as prose in the skill, not a config fraction) ===
if grep -q '^experiment_engineering:' "$CFG" \
   && grep -q 'skills: \[experiment-engineering\]' "$CFG" \
   && ! grep -q 'oom_headroom_frac: ' "$CFG"; then
  ok "config: experiment_engineering block exposes the skill (dead OOM knob stays deleted)"
else no "config: experiment_engineering block missing/incomplete (or dead oom knob resurrected)"; fi

# === Case 2: research.js reads the block (const) ===
if grep -q "need(CFG, 'experiment_engineering')" "$JS"; then
  ok "research.js: EXP_ENG = need(CFG,'experiment_engineering')"
else no "research.js: missing experiment_engineering const"; fi

# === Case 3: the experiment_worker goal injects the skill's bare name ===
if grep -q 'EXP_ENG.skills.join' "$JS"; then
  ok "research.js: experiment_worker goal injects EXP_ENG.skills"
else no "research.js: goal does not inject EXP_ENG.skills"; fi

# === Case 4: blanket no-smoke replaced by the probe-vs-scaled-down split ===
# (goal text extracted to plugins/experiment-lab-ar/spec/experiment-protocol.md — grep its new home)
if grep -q 'engineering PROBE' "$ESPEC" && grep -q 'scaled-down SCIENCE' "$ESPEC" \
   && ! grep -q '(NO smoke/scaled-down)' "$ESPEC"; then
  ok "experiment-protocol.md: blanket '(NO smoke/scaled-down)' replaced by the probe/scaled-down split"
else no "experiment-protocol.md: no-smoke split not applied (old blanket text still present?)"; fi

# === Case 5: SKILL.md present, named, has !`...` probe injection + probe/scaled-down section ===
if [ -f "$SK" ] && grep -q '^name: experiment-engineering' "$SK" \
   && grep -q 'hw.ncpu' "$SK" && grep -q 'Probe vs scaled-down' "$SK"; then
  ok "SKILL.md: present, named, has hardware-probe injection + probe/scaled-down section"
else no "SKILL.md: missing or incomplete"; fi

# === Case 6: the four reference files exist (progressive disclosure) ===
miss=""
for r in pytorch-single-gpu distributed-quantization-trl scientific-computing-gpu profiling-and-oom; do
  [ -f "$REF/$r.md" ] || miss="$miss $r"
done
if [ -z "$miss" ]; then ok "reference: all four deep-dive files present"
else no "reference: missing -$miss"; fi

# === Case 7: the injected probe commands actually run on THIS machine ===
CORES="$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null)"
if [ -n "$CORES" ] && [ "$CORES" -ge 1 ] 2>/dev/null; then
  ok "probe runs on this machine (cores=$CORES)"
else no "probe failed to read cores on this machine"; fi

echo "----"; echo "t15_experiment_engineering: $pass passed, $fail failed"; [ "$fail" = 0 ]
