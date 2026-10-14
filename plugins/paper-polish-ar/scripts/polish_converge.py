#!/usr/bin/env python3
r"""polish_converge — the DETERMINISTIC convergence + best-round decider for /polish.

`/polish`'s locked principle (spec/polish.js:30-32, invariant 6): convergence and best-round
selection are deterministic and OWNED by the spec — NEVER an LLM judgment. The agents return
verdicts (a fidelity verdict + quality flags, each tagged with a categorical severity + a
disposition); this script reduces them to a single CATEGORICAL STATE + the stop decision. In the
serial loop the orchestrator (an LLM) reproduces this "in its head"; in the parallel design a
section-runner subagent must decide whether to run another round. Letting EITHER reason about
convergence with an LLM violates rules-as-judge, so this script is the single decider: feed it a
round's verdicts (+ the prior rounds' states) and it returns the round's state and the stop
decision; feed it the full round list and it returns the best round. Both the serial path and the
section-runner call it, so the decision is identical and unit-testable. Stdin JSON in, stdout JSON
out, no config reads (every knob is passed in -> pure).

── the categorical model (D15: weighted scoring was REMOVED) ────────────────────────────────────
There is NO numeric severity weighting any more. A round collapses to ONE adjective — its STATE —
read off the WORST OPEN (non-deferred) quality flag:

    clean         no open actionable flag at all (the open set is empty)
    cosmetic-only only low-severity readability/tell flags remain (recurring_readability/minor_tell)
    has-core      a logic_core / results_core / ai_tells_systematic flag remains, OR a reviewer
                  reads the prose as machine-assembled (a systematic AI-tell floor)

D1: the per-round semantic-fidelity gate was REMOVED, so there is no `unrecoverable` state any more —
a round is one of clean / cosmetic-only / has-core. RANK keeps the `unrecoverable` key only for
backward-compat with old on-disk ledgers; the scorer never produces it.

Convergence is the strict EMPTY-SET model (Doc A §10-E, DECISIONS D9/D15): a section CONVERGES iff
its state is `clean` (no open actionable flag) AND full dimension coverage. A `cosmetic-only` round
NEVER stops on its own — the reviewer is licensed to mark a TRIVIAL cosmetic nitpick
`disposition='deferred'` (with a reason) after it has had at least one fix attempt, which drops it
out of the open set; once the residue is deferred the state becomes `clean` and the section
converges. Deferred flags are deliberately-kept / needs-author and are excluded from the state
exactly like they were excluded from the old weighted sum.

best-round is the pure categorical LADDER `clean > cosmetic-only > has-core`; ties resolve to the
LATEST round. (do-no-harm is gone — every section ALWAYS ships its best round; do_no_harm stays in
the output for back-compat and is now always false since no round is `unrecoverable`.) no_improvement
is categorical: the streak increments on any round whose state is not strictly better (higher on the
ladder) than the best seen so far.

── mode: "round" ──────────────────────────────────────────────────────────────
in : { mode, round, round_cap, dimensions[], no_improvement_rounds,
       history:[{state: "clean"|"cosmetic-only"|"has-core"}, ...],  # prior rounds, in order
       current:{ verdicts:{ quality:[{flags[],reads_like,dimensions_covered[]}] } } }
out: { state, open_count, coverage[], full_coverage,
       no_improvement_streak, stop, stop_reason }

── mode: "best" ───────────────────────────────────────────────────────────────
in : { mode, rounds:[{round, state}, ...] }
out: { best_round, best_state, do_no_harm }    # do_no_harm now always false (no `unrecoverable` round)
"""
import json
import sys

# [[MECH]] a quality flag whose severity is in this set is a CORE problem — it blocks `clean` and
# `cosmetic-only` (the section is `has-core` until it is fixed or deferred). Everything else
# (recurring_readability / minor_tell) is cosmetic.
NONCOSMETIC = {"logic_core", "results_core", "ai_tells_systematic"}

# [[MECH]] the ladder, worst -> best. best-round picks the MAX; no_improvement compares ranks. D1: the
# `unrecoverable` key is kept ONLY for backward-compat with old on-disk ledgers — it is never produced.
RANK = {"unrecoverable": 0, "has-core": 1, "cosmetic-only": 2, "clean": 3}


def actionable_flags(quality):
    """Every quality flag the reviewer did NOT defer, flattened across reviewers."""
    return [f for q in (quality or []) for f in (q.get("flags", []) or [])
            if f.get("disposition") != "deferred"]


def reads_machine(quality):
    """A reviewer read the prose as machine-assembled — a systematic AI-tell floor that holds the
    section at `has-core` even if only cosmetic flags are tagged."""
    qs = quality or []
    return any(q.get("reads_like") == "machine-assembled" for q in qs)


def covered_dimensions(quality):
    """Union of dimensions_covered across reviewers (order-preserving)."""
    seen = []
    for q in quality or []:
        for d in q.get("dimensions_covered", []) or []:
            if d not in seen:
                seen.append(d)
    return seen


def round_state(quality):
    """[[MECH]] collapse a round's verdicts to its categorical STATE (the worst open concern).
    D1: the per-round semantic-fidelity gate was removed, so there is no `unrecoverable` state any more —
    a round is one of clean / cosmetic-only / has-core, read off the quality reviewers' open flags."""
    flags = actionable_flags(quality)
    if any(f.get("severity") in NONCOSMETIC for f in flags) or reads_machine(quality):
        return "has-core"
    if flags:                      # only low-severity readability/tell flags remain
        return "cosmetic-only"
    return "clean"                 # the open set is empty


def no_improvement_streak(state_seq):
    """[[MECH]] the streak AFTER the final round: it resets to 0 on any round that climbs STRICTLY
    higher on the ladder than the best seen so far, and increments otherwise. prev_best starts below
    the floor (-1) so round 1 always counts as an improvement (streak 0), mirroring the old
    weighted-falling streak."""
    streak, prev_best = 0, -1
    for st in state_seq:
        r = RANK.get(st, 0)
        if r > prev_best:
            streak = 0
            prev_best = r
        else:
            streak += 1
    return streak


def run_round(data):
    dimensions = data.get("dimensions", []) or []
    no_improve = data.get("no_improvement_rounds", 2)
    round_no = data.get("round", 1)
    round_cap = data.get("round_cap", round_no)
    history = data.get("history", []) or []
    cur = data.get("current", {}) or {}

    verdicts = cur.get("verdicts", {}) or {}
    quality = verdicts.get("quality", []) or []

    state = round_state(quality)
    open_count = len(actionable_flags(quality))
    coverage = covered_dimensions(quality)
    full_coverage = all(d in coverage for d in dimensions)

    seq = [h.get("state") for h in history] + [state]
    streak = no_improvement_streak(seq)

    # CONVERGE decision — empty-set model (D1: no fidelity gate). A `cosmetic-only` round NEVER stops
    # here; the reviewer defers the trivial residue (-> the open set empties -> `clean`) or iterates.
    converged = (state == "clean") and full_coverage
    stop, reason = False, None
    if converged:
        stop, reason = True, "clean"
    elif streak >= no_improve:
        stop, reason = True, "no_improvement"
    elif round_no >= round_cap:
        stop, reason = True, ("light_single_pass" if round_cap == 1 else "max_rounds")

    return {
        "state": state,
        "open_count": open_count,
        "coverage": coverage,
        "full_coverage": full_coverage,
        "no_improvement_streak": streak,
        "stop": stop,
        "stop_reason": reason,
    }


def run_best(data):
    """SHIP BEST: the highest round on the ladder `clean > cosmetic-only > has-core`; ties resolve to
    the LATEST round. D1: do_no_harm is retained for back-compat but is now always false (no round is
    `unrecoverable`) — the caller ALWAYS ships the best round."""
    rounds = data.get("rounds", []) or []
    if not rounds:
        return {"best_round": None, "best_state": None, "do_no_harm": True}
    best = rounds[0]
    for r in rounds[1:]:
        if RANK.get(r.get("state"), 0) >= RANK.get(best.get("state"), 0):
            best = r                 # >= keeps the LATEST round on a tie
    bs = best.get("state")
    return {
        "best_round": best.get("round"),
        "best_state": bs,
        "do_no_harm": all(RANK.get(r.get("state"), 0) == 0 for r in rounds),
    }


def main():
    data = json.load(sys.stdin)
    mode = data.get("mode", "round")
    out = run_best(data) if mode == "best" else run_round(data)
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
