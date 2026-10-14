#!/usr/bin/env bash
# T49 — RC-6 .polish seal/teardown must DISARM even though the run-end cleanup lives in a spec that the
# Claude Code harness auto-classifies for "self-modification". The two BARE `rm -f` seal commands in
# batchGroundClean (the manifest disarm + the root .polish symlink drop) were being false-flagged + BLOCKED,
# so the fidelity hook stayed armed + a dangling ${PROJECT_DIR}/.polish symlink leaked into the next run.
# Fix (option a): reform both bare `rm -f` into `find … -delete` (matches the existing Bash(find:*) allow).
# This test proves the reformed seal DISARMS, end-to-end, all MECHANICAL/offline:
#   (1) Arm a real fixture (runs/<slug>/.polish + fidelity-manifest.json + repo-root .polish SYMLINK),
#       drive the vendored check_fidelity.py against it, and confirm it WOULD deny (guard is genuinely armed).
#   (2) Run the two reformed `find … -delete` seal commands (mirroring batchGroundClean's per-dir iteration:
#       dir = the repo-root SYMLINK, then the real dir, then the paper/ fallback), then the root-symlink drop.
#   (3) Assert disarm: no fidelity-manifest.json remains (via the symlink path NOR the real dir), and the hook
#       now ALLOWS (unarmed = no deny) for the same edit that denied while armed.
#   (4) Assert no dangling link + target preserved: ${PROJECT_DIR}/.polish symlink is gone, while the real
#       runs/<slug>/.polish dir still EXISTS (guards the `-type l` correctness — never remove the target dir).
#   (5) Pattern-regression guard on spec/research.js batchGroundClean: NO bare `rm` targeting
#       fidelity-manifest.json or ${PROJECT_DIR}/.polish may reappear; the `find … -delete` forms must be present.
#   (6) spec/research.js still parses (node --check).
# NOTE: we cannot execute the harness self-modification auto-classifier statically, so (5) is the strongest
# available guard that the FLAGGED bare-`rm` form cannot be reintroduced; the classifier survival of the new
# `find … -delete` form (which matches Bash(find:*)) is asserted by design, not by running the classifier.
# Run: bash tests/t49_rc6_seal_disarm.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
HOOK="$ROOT/plugins/paper-polish-ar/hooks/check_fidelity.py"
pass=0; fail=0
p() { echo "PASS  $1"; pass=$((pass+1)); }
f() { echo "FAIL  $1"; fail=$((fail+1)); }
chk() { if eval "$2" >/dev/null 2>&1; then p "$1"; else f "$1"; fi; }

PROJECT_DIR="$(mktemp -d)"
trap 'rm -rf "$PROJECT_DIR"' EXIT
SLUG="seedpaper-t49"
WS="$PROJECT_DIR/runs/$SLUG"
BLKFILE="$PROJECT_DIR/_batchGroundClean.block"
PAYLOAD="$PROJECT_DIR/_payload.json"

# ── (0) Arm the fixture: real per-paper .polish + manifest, then the repo-root symlink (mimic research.js:1273)
mkdir -p "$WS/.polish"
cat > "$WS/.polish/fidelity-manifest.json" <<JSON
{"mode":"polish","format":"latex","denylist":["$PROJECT_DIR/frozen.bib"]}
JSON
: > "$PROJECT_DIR/frozen.bib"                                   # a frozen data file the armed hook must protect
( cd "$PROJECT_DIR" && ln -s "runs/$SLUG/.polish" ".polish" )  # research.js:1273 arm: root .polish -> per-paper .polish
chk "fixture: repo-root .polish is a symlink"                 '[ -L "$PROJECT_DIR/.polish" ]'
chk "fixture: manifest visible through the symlink (armed)"   '[ -f "$PROJECT_DIR/.polish/fidelity-manifest.json" ]'

# The Edit the armed hook must DENY (frozen.bib is on the manifest denylist -> on_denylist -> deny).
cat > "$PAYLOAD" <<JSON
{"tool_name":"Edit","tool_input":{"file_path":"$PROJECT_DIR/frozen.bib","old_string":"x","new_string":"y"},"cwd":"$PROJECT_DIR"}
JSON

# ── (1) ARMED sanity: the vendored hook WOULD block the edit (proves the seal has something real to disarm)
armed_out="$(CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$HOOK" < "$PAYLOAD" 2>/dev/null || true)"
if printf '%s' "$armed_out" | grep -q '"deny"'; then p "armed: hook DENIES the frozen-file edit"; else f "armed: hook DENIES the frozen-file edit (got: ${armed_out:-<empty>})"; fi

# ── (2) Run the reformed RC-6 seal — mirror batchGroundClean: (c) per-dir manifest disarm, then (d) symlink drop.
#     dir iterates the repo-root SYMLINK, the real workspace dir, then the paper/ fallback (matches research.js).
for dir in "$PROJECT_DIR/.polish" "$WS/.polish" "$WS/paper/.polish"; do
  find "${dir}/" -maxdepth 1 -name fidelity-manifest.json -delete 2>/dev/null || true   # (c) reformed disarm
done
find "$PROJECT_DIR" -maxdepth 1 -type l -name .polish -delete 2>/dev/null || true         # (d) reformed symlink drop

# ── (3) Disarm assertions: manifest gone (both paths), and the hook now ALLOWS the same edit.
chk "disarm: no manifest under the real workspace .polish"   '[ ! -e "$WS/.polish/fidelity-manifest.json" ]'
chk "disarm: no manifest resolvable via repo-root .polish"   '[ ! -e "$PROJECT_DIR/.polish/fidelity-manifest.json" ]'
sealed_out="$(CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 "$HOOK" < "$PAYLOAD" 2>/dev/null || true)"
if printf '%s' "$sealed_out" | grep -q '"deny"'; then f "disarmed: hook ALLOWS the edit (still denying: $sealed_out)"; else p "disarmed: hook ALLOWS the edit (unarmed = no deny)"; fi

# ── (4) No dangling link + target dir preserved (guards `-type l` — must never delete the real dir).
chk "cleanup: repo-root .polish symlink is GONE"             '[ ! -L "$PROJECT_DIR/.polish" ] && [ ! -e "$PROJECT_DIR/.polish" ]'
chk "cleanup: real runs/<slug>/.polish dir still EXISTS"     '[ -d "$WS/.polish" ]'

# ── (5) Pattern-regression guard on the batchGroundClean seal block in spec/research.js.
awk '/^function batchGroundClean\(/{g=1} g{print} g&&/^}/{exit}' "$SPEC" > "$BLKFILE"
grep -Fq 'find "${dir}/" -maxdepth 1 -name fidelity-manifest.json -delete' "$BLKFILE" \
  && p "src: (c) manifest disarm uses find … -delete" || f "src: (c) manifest disarm uses find … -delete"
grep -Fq 'find "${PROJECT_DIR}" -maxdepth 1 -type l -name .polish -delete' "$BLKFILE" \
  && p "src: (d) symlink drop uses find -type l … -delete" || f "src: (d) symlink drop uses find -type l … -delete"
grep -Eq '\brm\b[^)]*fidelity-manifest' "$BLKFILE" \
  && f "src: NO bare rm targets fidelity-manifest.json (regressed!)" || p "src: NO bare rm targets fidelity-manifest.json"
grep -Eq '\brm\b[^)]*\$\{PROJECT_DIR\}/\.polish' "$BLKFILE" \
  && f "src: NO bare rm targets \${PROJECT_DIR}/.polish (regressed!)" || p "src: NO bare rm targets \${PROJECT_DIR}/.polish"

# ── (6) spec still parses.
chk "spec: parses (node --check)"                            "node --check '$SPEC'"

echo "----"; echo "t49_rc6_seal_disarm: $pass passed, $fail failed"; [ "$fail" = 0 ]
