#!/usr/bin/env python3
"""Unit tests for scripts/polish_converge.py — the deterministic CATEGORICAL convergence + best-round
decider (D15: numeric weighting was removed; D1: the per-round semantic-fidelity gate was removed).

Covers: state collapse (clean / cosmetic-only / has-core), the empty-set convergence model (state=='clean'
&& full_coverage — there is NO fidelity term any more), the FLOORs that hold a section at has-core (a core
flag / a machine-assembled read), deferred flags leaving the open set, the cosmetic-only round NOT stopping
on its own, no_improvement (categorical), partial coverage suppressing `clean`, best-round laddering with
ties->latest, and "always ship best" (do-no-harm is gone — best mode never sends the caller to the original,
and a missing fidelity field never errors). Pure stdin/stdout subprocess calls — exactly how the spec
invokes the script.

Run:  python3 scripts/test_polish_converge.py
"""
import json
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "polish_converge.py")
DIMS = ["logic", "results", "readability", "ai-tells"]
ALLDIMS = [{"dimensions_covered": DIMS, "flags": [], "reads_like": "human-expert"}]

failures = []


def call(payload):
    r = subprocess.run([sys.executable, SCRIPT], input=json.dumps(payload),
                       capture_output=True, text=True)
    assert r.returncode == 0, f"script exited {r.returncode}: {r.stderr}"
    return json.loads(r.stdout)


def rnd(current_quality, *, round=1, round_cap=2, history=None):
    # D1: `current` carries ONLY {verdicts:{quality}} — no `unrecoverable`, no `fidelity`.
    return call({
        "mode": "round", "round": round, "round_cap": round_cap,
        "dimensions": DIMS, "no_improvement_rounds": 2, "history": history or [],
        "current": {"verdicts": {"quality": current_quality}},
    })


def check(label, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        failures.append(label)


def q(flags, reads_like="human-expert", dims=DIMS):
    return [{"dimensions_covered": dims, "flags": flags, "reads_like": reads_like}]


def main():
    # 1. clean: full coverage, no open flag -> the open set is empty -> converge (state=='clean' &&
    #    full_coverage; D1: no fidelity term in the convergence decision).
    o = rnd(ALLDIMS)
    check("1a clean state", o["state"], "clean")
    check("1b clean open_count", o["open_count"], 0)
    check("1c clean full_coverage", o["full_coverage"], True)
    check("1d clean stop", o["stop"], True)
    check("1e clean stop_reason", o["stop_reason"], "clean")

    # 2. cosmetic-only: only a low-severity tell remains -> state cosmetic-only and it does NOT stop on
    #    its own (the reviewer must defer the trivial residue, which empties the open set). Iterates.
    o = rnd(q([{"severity": "minor_tell", "dimension": "ai-tells", "issue": "lone However,"}],
              reads_like="competent-but-flat"), round=1, round_cap=3)
    check("2a cosmetic-only state", o["state"], "cosmetic-only")
    check("2b cosmetic-only open_count", o["open_count"], 1)
    check("2c cosmetic-only does NOT stop", o["stop"], False)

    # 3. FLOOR: a core flag holds the section at has-core (never clean/cosmetic-only).
    o = rnd(q([{"severity": "logic_core", "dimension": "logic", "issue": "broken funnel"}]),
            round=1, round_cap=2)
    check("3a core state", o["state"], "has-core")
    check("3b core does not stop early", o["stop"], False)
    check("3c core open_count", o["open_count"], 1)

    # 4. FLOOR: a machine-assembled read holds the section at has-core even with only cosmetic flags.
    o = rnd(q([{"severity": "minor_tell", "dimension": "ai-tells", "issue": "x"}],
              reads_like="machine-assembled"))
    check("4 machine-assembled -> has-core", o["state"], "has-core")

    # 5. deferred flags leave the open set: a deferred core flag + a deferred cosmetic flag -> open set
    #    empty -> clean (deferred is excluded from the state exactly like the old weighted exclusion).
    o = rnd(q([{"severity": "logic_core", "disposition": "deferred", "issue": "kept on purpose"},
               {"severity": "minor_tell", "disposition": "deferred", "issue": "trivial nit deferred"}]))
    check("5a all-deferred open_count", o["open_count"], 0)
    check("5b all-deferred -> clean", o["state"], "clean")
    check("5c all-deferred converges", o["stop_reason"], "clean")

    # 5'. D-2: a cosmetic flag NOT yet deferred keeps the section cosmetic-only (it earns its attempt);
    #     deferring the trivial residue is what empties the open set.
    o = rnd(q([{"severity": "minor_tell", "disposition": "actionable", "issue": "still trying"},
               {"severity": "recurring_readability", "disposition": "deferred", "issue": "deferred nit"}]))
    check("5'a one actionable cosmetic left -> cosmetic-only", o["state"], "cosmetic-only")
    check("5'b open_count counts only the actionable one", o["open_count"], 1)

    # 6. no_improvement (categorical): the state did not climb the ladder for 2 consecutive rounds.
    #    round 3 has-core with history has-core, has-core -> streak 2 -> stop no_improvement (cap left
    #    high so no_improvement, not max_rounds, is the reason). A machine read keeps it at has-core.
    flags = [{"severity": "recurring_readability", "disposition": "actionable", "issue": "flat"}]
    o = rnd(q(flags, reads_like="machine-assembled"), round=3, round_cap=5,
            history=[{"state": "has-core"}, {"state": "has-core"}])
    check("6a no_improve state", o["state"], "has-core")
    check("6b no_improve streak", o["no_improvement_streak"], 2)
    check("6c no_improve stop_reason", o["stop_reason"], "no_improvement")

    # 6'. an improving round (has-core -> cosmetic-only climbs the ladder) resets the streak.
    o = rnd(q(flags, reads_like="competent-but-flat"), round=2, round_cap=3,
            history=[{"state": "has-core"}])
    check("6'a improving streak resets", o["no_improvement_streak"], 0)
    check("6'b improving does not stop", o["stop"], False)

    # 7. max_rounds: reached the cap with work still open.
    o = rnd(q(flags, reads_like="machine-assembled"), round=2, round_cap=2,
            history=[{"state": "has-core"}])
    check("7 max_rounds at cap", o["stop_reason"], "max_rounds")

    # 7'. light single pass: round_cap==1 reports light_single_pass (keynote effort=light).
    o = rnd(q(flags, reads_like="machine-assembled"), round=1, round_cap=1)
    check("7' light_single_pass", o["stop_reason"], "light_single_pass")

    # 8. D1: a missing fidelity field never errors and never blocks — `current` carries only quality, and
    #    a clean quality verdict still converges (no fidelity term in the decision).
    o = call({"mode": "round", "round": 1, "round_cap": 2, "dimensions": DIMS,
              "no_improvement_rounds": 2, "history": [],
              "current": {"verdicts": {"quality": ALLDIMS}}})   # NOTE: no "fidelity" key, no "unrecoverable"
    check("8a no fidelity field -> clean state", o["state"], "clean")
    check("8b no fidelity field -> converges", o["stop_reason"], "clean")

    # 9. partial coverage suppresses `clean` convergence even with an empty open set.
    o = rnd(q([], dims=["logic", "results"]))
    check("9a partial full_coverage false", o["full_coverage"], False)
    check("9b partial state still clean (no open flag)", o["state"], "clean")
    check("9c partial does NOT converge (coverage gate)", o["stop"], False)

    # 10. best-round: highest on the ladder wins; ties resolve to the LATEST round.
    o = call({"mode": "best", "rounds": [{"round": 1, "state": "has-core"},
                                         {"round": 2, "state": "clean"},
                                         {"round": 3, "state": "clean"}]})
    check("10a best highest, tie->latest", o["best_round"], 3)
    check("10b best state", o["best_state"], "clean")
    check("10c best not do_no_harm", o["do_no_harm"], False)

    # 11. ALWAYS ship best (D1: do-no-harm is gone). Even an all-has-core run ships its best round and is
    #     never routed to the original — do_no_harm stays false.
    o = call({"mode": "best", "rounds": [{"round": 1, "state": "has-core"},
                                         {"round": 2, "state": "has-core"}]})
    check("11a all-has-core ships best (latest tie)", o["best_round"], 2)
    check("11b all-has-core not do_no_harm", o["do_no_harm"], False)

    # 12. ALWAYS ship best across mixed live states — clean beats cosmetic-only beats has-core; never
    #     do-no-harm regardless of order.
    o = call({"mode": "best", "rounds": [{"round": 1, "state": "cosmetic-only"},
                                         {"round": 2, "state": "has-core"}]})
    check("12a cosmetic-only beats later has-core", o["best_round"], 1)
    check("12b not do_no_harm", o["do_no_harm"], False)

    # 13. best across a cosmetic-only vs has-core vs clean mix -> clean wins.
    o = call({"mode": "best", "rounds": [{"round": 1, "state": "cosmetic-only"},
                                         {"round": 2, "state": "clean"},
                                         {"round": 3, "state": "has-core"}]})
    check("13 best picks clean over later has-core", o["best_round"], 2)

    # 14. back-compat: RANK still knows `unrecoverable` (rank 0) so an OLD on-disk ledger that recorded
    #     it still ranks correctly (lowest) — even though the scorer never produces it any more.
    o = call({"mode": "best", "rounds": [{"round": 1, "state": "unrecoverable"},
                                         {"round": 2, "state": "has-core"}]})
    check("14 legacy unrecoverable ranks lowest -> has-core wins", o["best_round"], 2)

    print()
    if failures:
        print(f"FAILED: {len(failures)} assertion(s): {', '.join(failures)}")
        return 1
    print("polish_converge.py: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
