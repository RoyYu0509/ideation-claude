#!/usr/bin/env bash
# bin/setup_workspace.sh — the ONE-TIME destructive workspace bootstrap, extracted from the old
# setupWorkspace() JS body so the L0 orchestrator (spec/research.js, the `setup_workspace` stage) calls it
# as a single deterministic tool-call. Mirrors the bin/ discipline (reopen_noop_diff.sh / audit_artifact_*):
# the pure mechanical work lives HERE; the thin spec only resolves the venue→skeleton path and passes args.
#
# SELF-GUARDED / IDEMPOTENT: milestone-state.json is the L0-owned sentinel for "workspace already built". On
# any 2nd+ call (a resume re-entering the setup_workspace stage) it exits 0 at once — re-running the cp/git
# would clobber the drafted paper, truncate the living logs, and reset the milestone ledger the ship-gate
# provenance rests on. The caller (research.js) still runs assertGitInit(ws) AFTER this as the RC-10 hard-stop.
#
# Args:  <ws> <skeleton_dir> <protocol_src> <config_yaml> <spec_commit>
#   ws            = runs/<slug> workspace root (slug is derived as its basename)
#   skeleton_dir  = venue-keyed LaTeX skeleton dir (resolveSkeleton already chose it; we cp its contents)
#   protocol_src  = absolute path to research-protocol.md (the operating constitution)
#   config_yaml   = absolute path to config/config.yaml (frozen + sha-stamped here)
#   spec_commit   = the spec repo HEAD sha (research.js computes it; "unknown" if unavailable)
# Exit: 0 = built (or already built, no-op); 2 = bad args.
set -euo pipefail

WS="${1:-}"; SKEL="${2:-}"; PROTO="${3:-}"; CFG="${4:-}"; SPEC_COMMIT="${5:-unknown}"
[ -n "$WS" ] && [ -n "$SKEL" ] && [ -n "$PROTO" ] && [ -n "$CFG" ] || {
  echo "ERROR setup_workspace: usage: $0 <ws> <skeleton_dir> <protocol_src> <config_yaml> <spec_commit>" >&2; exit 2; }

# [[MECH]] GUARD: built once already → NEVER re-run the destructive build (the milestone-state.json sentinel).
[ -f "$WS/milestone-state.json" ] && exit 0

SLUG="$(basename "$WS")"

mkdir -p "$WS/code/reference" "$WS/paper" "$WS/EXPERIMENTS"   # workspace skeleton
cp -R "$SKEL/." "$WS/paper/"                                  # venue-keyed LaTeX skeleton
cp -f "$PROTO" "$WS/RESEARCH-PROTOCOL.md"                     # operating constitution
: > "$WS/RESEARCH_LOG.md"; : > "$WS/DECISIONS.md"; : > "$WS/FAILURES.md"

git -C "$WS/code" init -q; git -C "$WS/paper" init -q         # provenance needs git
# workspace-root git tracks RESEARCH_LOG / HANDOFF / DECISIONS / FAILURES / EXPERIMENTS / milestone-state;
# paper/ and code/ are nested repos excluded via .gitignore so they keep their own histories.
git -C "$WS" init -q; printf 'code/\npaper/\n' > "$WS/.gitignore"

# [[MECH]] RC-8/RC-9: freeze a per-paper snapshot + sha-stamp of config + protocol + spec so mid-run mutation
# is instantly visible, and lay the baseline commit BOTH milestoneDone (RC-3) and the B3 disk-derived gate
# (RC-4) rest on. milestone-state.json is L0-OWNED.
cp -f "$CFG" "$WS/.config-frozen.yaml"
CFG_SHA="$(shasum -a 256 "$CFG" | cut -d' ' -f1)"
PROTO_SHA="$(shasum -a 256 "$WS/RESEARCH-PROTOCOL.md" | cut -d' ' -f1)"
AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

SLUG="$SLUG" CFG_SHA="$CFG_SHA" PROTO_SHA="$PROTO_SHA" SPEC_COMMIT="$SPEC_COMMIT" AT="$AT" \
  python3 - "$WS/milestone-state.json" <<'PY'
import os, sys, json
out = sys.argv[1]
doc = {
    "schema": "auto-research-milestone@1",
    "paper_slug": os.environ["SLUG"],
    "frozen": {
        "config_sha256":   os.environ["CFG_SHA"],
        "protocol_sha256": os.environ["PROTO_SHA"],
        "spec_commit":     os.environ["SPEC_COMMIT"],
        "at":              os.environ["AT"],
    },
    "milestones": {},
}
with open(out, "w") as f:
    json.dump(doc, f, indent=2)
    f.write("\n")
PY

git -C "$WS/code"  add -A && git -C "$WS/code"  commit -qm "baseline: env init"            --allow-empty
git -C "$WS/paper" add -A && git -C "$WS/paper" commit -qm "baseline: skeleton + protocol" --allow-empty
git -C "$WS"       add -A && git -C "$WS"       commit -qm "baseline: workspace init"      --allow-empty
