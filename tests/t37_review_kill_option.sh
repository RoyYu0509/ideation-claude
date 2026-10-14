#!/usr/bin/env bash
# t37 — review escalation strategic-kill 格: a lethality:fatal item must be ABLE to surface the worth-it/kill
# disposition, a non-fatal item must NOT, and review only SURFACES it (L0 enacts via rescue-first). Before this
# 格 the menu structurally lacked kill, so the investigator's fatal verdict never reached the owner (the
# strategic-kill bug). Since 2026-07-05 the escalation registry is a PROSE contract in the review protocol's
# output contract (review.js retired) — assert the text contract carries every load-bearing clause.
# Run: bash tests/t37_review_kill_option.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
chk(){ if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
OC="$ROOT/plugins/paper-polish-ar/spec/review/output-contract.md"
PROTO="$ROOT/plugins/paper-polish-ar/spec/review-protocol.md"

chk "output contract exists"                                  "test -f '$OC'"
chk "registry carries the worth_it disposition"               "grep -Fq 'worth_it' '$OC'"
chk "worth_it maps to the kill executor_kind"                 "grep -Eq 'worth_it.*\|.*kill' '$OC'"
chk "kill option is gated to FATAL items only"                "grep -Fq 'fatal items only' '$OC'"
chk "fatal gating is an ENSURE rule (menu injection)"         "grep -Eq 'lethality: fatal.*ensure|ensure the .worth_it. option' '$OC'"
chk "review only SURFACES the kill (never enacts)"            "grep -Fq 'never enacts a kill' '$OC'"
chk "kill routes through rescue FIRST (residual of failed rescue)" "grep -Fq 'kill is the residual of a failed rescue' '$OC'"
chk "closed set: the registry is the ONLY disposition source" "grep -Fq 'CLOSED disposition set' '$OC'"
chk "protocol pins the closed set as a non-negotiable"        "grep -Fq 'Closed disposition set' '$PROTO'"
chk "minor needs_author is recorded, never escalated"         "grep -Fq 'never asked, never escalated' '$OC'"

echo "----"; echo "t37_review_kill_option: $pass passed, $fail failed"; [ "$fail" -eq 0 ]
