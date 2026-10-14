#!/usr/bin/env bash
# tests/run_all.sh — single entry point for the auto-research test suite (RC-8: there was NO runner/CI, so
# t5 FAILed unnoticed for days). Runs every test, prints a summary, exits non-zero if ANY fails. A test
# with an unmet ENV dependency (t7 needs a TeX install) is SKIPPED LOUDLY — never silently passed.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS=(test_loop_gate t2_hook_logic t3_detach_rewake t4_decision_roundtrip t5_vendored_load \
       t6_batch t7_skeletons t8_verify_panel t9_gate_derive t10_envelope_schema t11_freetext_input \
       t12_scan_orphan_stops t13_log_event t14_run_report t15_experiment_engineering \
       t16_polish_stage t17_resume_detached t19_crash_surface \
       t20_round_concern_snapshot \
       t24_ledger_open_reopen t25_per_round_reference_shrink \
       t27_concern_map_presence t29_polish_ledger_and_state \
       t30_audited_values_register t31_consolidate_mode t32_pipeline_status t33_ship_gate \
       t34_layer_split t35_audit_artifact_integrity t36_ambition_reconcile t37_review_kill_option \
       t38_loop_forward_motion t39_ambition_amplify t40_meta_loop_reauthor \
       t41_detach_pidfile_contract t42_archive_decision t43_lock_contracts t44_round_setup \
       t45_decision_guard_hook t46_milestone_done_provenance t47_enactment_wiring \
       t48_loop_round_counter t49_rc6_seal_disarm t50_ideation_integrity \
       t51_terminal_gate t52_verify_preflight t53_lock_guard_hook t54_git_sweep_guard \
       t55_review_protocol t56_session_capture t57_figure_design t58_seed_novelty_upgrade \
       t59_learn_resolve t60_learn_manifest t61_run_report_rollup t62_learn_hypotheses t63_learn_wiring \
       t64_learn_manifest_drift t65_quality_ledger t66_pool_snapshot t67_evidence_ceiling
       t68_classify_crash t69_transient_capture t70_verification_record t71_export_site_data \
       t72_ideation_spawn_guard \
       t73_central_ambition_guard t74_concern_prose_lint t75_capacity_readout \
       t76_spec_freeze t77_negative_policy t78_gate_adjudication t79_owner_direction_gate \
       t81_instance_identity \
       t6x_verdict_fidelity)
pass=0; fail=0; skip=0; failed=()
for t in "${TESTS[@]}"; do
  f="$ROOT/tests/$t.sh"
  if [ ! -f "$f" ]; then echo "SKIP  $t (file missing)"; skip=$((skip+1)); continue; fi
  if [ "$t" = "t7_skeletons" ] && ! command -v pdflatex >/dev/null 2>&1; then
    echo "SKIP  $t (pdflatex not installed)"; skip=$((skip+1)); continue
  fi
  if bash "$f" >"/tmp/ar-$t.out" 2>&1; then
    echo "PASS  $t"; pass=$((pass+1))
  else
    echo "FAIL  $t  (see /tmp/ar-$t.out)"; tail -2 "/tmp/ar-$t.out" | sed 's/^/        /'; fail=$((fail+1)); failed+=("$t")
  fi
done
echo "========================================"
echo "run_all: $pass passed, $fail failed, $skip skipped"
[ "$fail" = 0 ] || { echo "FAILED: ${failed[*]}"; exit 1; }
