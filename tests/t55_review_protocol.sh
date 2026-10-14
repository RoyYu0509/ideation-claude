#!/usr/bin/env bash
# T55 — the REVIEW-OWNER protocol chain (review.js retired 2026-07-05; design dev/review-protocol-design.md).
# Locks the load-bearing wiring + the non-negotiables' presence so a future edit cannot silently drop them:
#   (1) the protocol + its three leaves exist and carry their key contracts;
#   (2) the five non-negotiables' anchor phrases are present (cold-read / grounding / floor=2 / diagnose-only /
#       output contract) + the closed disposition set;
#   (3) both entries point at the protocol (commands/review.md standalone; config paths.review_spec +
#       REVIEW-L0-CONTRACT in-loop) and nothing points at the retired review.js;
#   (4) no model-name leaks into the new spec files (config is the model SSOT — B1-7);
#   (5) review.js and review-comprehension.md are gone from the live spec tree.
# Run: bash tests/t55_review_protocol.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
chk(){ if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
not(){ if eval "$2"; then echo "FAIL  $1"; fail=$((fail+1)); else echo "PASS  $1"; pass=$((pass+1)); fi; }

PP="$ROOT/plugins/paper-polish-ar"
PROTO="$PP/spec/review-protocol.md"
OC="$PP/spec/review/output-contract.md"
AC="$PP/spec/review/attack-classes.md"
CL="$PP/spec/review/checklist-pass.md"
CMD="$PP/commands/review.md"
L0C="$ROOT/spec/spawn-prompts/REVIEW-L0-CONTRACT.md"

# (1) the chain exists
chk "protocol exists"        "test -f '$PROTO'"
chk "output-contract leaf"   "test -f '$OC'"
chk "attack-classes leaf"    "test -f '$AC'"
chk "checklist-pass leaf"    "test -f '$CL'"

# (2) non-negotiables anchored in the protocol
chk "N1 diagnose-only + manifest arm"      "grep -Fq 'DIAGNOSE-ONLY' '$PROTO' && grep -Fq 'build_manifest.py' '$PROTO'"
chk "N2 cold-read topology"                "grep -Fq 'COLD-READ topology' '$PROTO'"
chk "N3 grounding floor (verbatim quote)"  "grep -Fq 'VERBATIM quote' '$PROTO' && grep -Fq 'verify_panel' '$PROTO'"
chk "N4 independence floor = TWO"          "grep -Fq 'TWO independent cold reads' '$PROTO'"
chk "N4 width has NO config knob"          "grep -Fq 'no config knob' '$PROTO'"
chk "N5 output contract binding"           "grep -Fq 'review/output-contract.md' '$PROTO'"
chk "N6 closed disposition set"            "grep -Fq 'Closed disposition set' '$PROTO'"
chk "owner reads the whole paper itself"   "grep -Fq 'Read the paper yourself' '$PROTO'"
chk "depth mandate + attack classes wired" "grep -Fq 'DEPTH MANDATE' '$PROTO' && grep -Fq 'review/attack-classes.md' '$PROTO'"
chk "checklist routes to synthesis only"   "grep -Fq 'never to reviewers' '$PROTO' || grep -Fq 'never into a reviewer' '$CL'"
chk "attack classes carry the W28 lessons" "grep -Fq 'True-by-construction' '$AC' && grep -Fq 'Trivially-true-on-this-data' '$AC' && grep -Fq 'Spin' '$AC'"
chk "oracle file review-verdicts.md pinned" "grep -Fq 'review-verdicts.md' '$OC'"

# (3) both entries point at the protocol; nothing at review.js
chk "standalone entry cats the protocol"   "grep -Fq 'spec/review-protocol.md' '$CMD'"
not "standalone entry no longer reads review.js" "grep -Fq 'spec/review.js' '$CMD'"
chk "config paths.review_spec -> protocol" "grep -Eq 'review_spec:.*review-protocol\.md' '$ROOT/config/config.yaml'"
chk "L0 contract executes the protocol"    "grep -Fq '<REVIEW_SPEC>' '$L0C' && grep -Fq 'REVIEW OWNER' '$L0C'"
chk "L0 contract keeps the ledger write"   "grep -Fq 'TASK_STATUS.concerns.json' '$L0C'"
chk "L0 contract keeps redesign routing"   "grep -Fq 'HANDOFF-redesign-' '$L0C'"
chk "L0 contract keeps contribution-hollow id" "grep -Fq \"id:'contribution-hollow'\" '$L0C'"
chk "research.js spawns the owner via the contract" "grep -Fq 'REVIEW-L0-CONTRACT.md' '$ROOT/spec/research.js'"

# (4) config is the model SSOT — no model names in the new spec chain (B1-7)
not "no model-name leak in the review chain" "grep -riEq 'opus|sonnet|haiku' '$PROTO' '$OC' '$AC' '$CL' '$L0C'"

# (5) the retired files are gone from the live tree
not "review.js retired from spec/"                 "test -f '$PP/spec/review.js'"
not "review-comprehension.md retired"              "test -f '$PP/spec/spawn-prompts/review-comprehension.md'"
chk "checklist role exists in config roles"        "grep -Fq 'checklist:' '$PP/config/config.yaml'"
not "comprehender role removed from config roles"  "grep -Eq '^\s*comprehender:' '$PP/config/config.yaml'"

echo "----"; echo "t55_review_protocol: $pass passed, $fail failed"; [ "$fail" -eq 0 ]
