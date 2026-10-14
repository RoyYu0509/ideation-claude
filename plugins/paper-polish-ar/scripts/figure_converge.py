#!/usr/bin/env python3
r"""figure_converge — the DETERMINISTIC per-FIGURE convergence + best-round decider for /polish-figures.

The MIRROR of scripts/polish_converge.py (which does the same job for /polish sections). /polish-figures'
locked principle (spec/polish-figures.js:19-21): convergence and best-version selection are PURE ARITHMETIC
owned by the spec and NEVER an LLM judgment — the agents return verdicts (a THREE-WAY fidelity verdict +
visual-QA flags), and this script reduces them to the stop decision + the best round. BOTH paths call it
(dossier-12 G1: the serial orchestrator's inline arithmetic was retired 2026-07-06 — serial and the L2
figure_runner now issue the same figure-loop.md §6/§7 heredoc calls). Letting EITHER reason about
convergence with an LLM violates rules-as-judge, so this script is the single decider — feed it a round's
(fidelity_verdict + actionable count) plus the prior rounds and it returns the round's state + the stop
decision; feed it the full round list and it returns the best round. Identical decisions + unit-testable.
Stdin JSON in, stdout JSON out, no config reads (every knob is passed in -> pure).

── the figure model (mirrors runFigure, spec/polish-figures.js) ──────────────────────────────────────────
A round collapses to ONE of three states, read off the fidelity verdict + the actionable visual-flag count
the CALLER computed (non-deferred flags, plus any baseline_conflict flag and the mandated annotation
crop-check backstop flag — that counting stays with the caller; this script only reduces the totals):

    reverted     fidelity verdict is FAIL (suspected data drift) or HOLD (a numeric/scale rescale held for
                 author approval) -> this round is do-no-harm reverted, un-shippable (actionable = ∞).
    clean        fidelity PASS AND zero actionable visual flag remain -> faithful + clean.
    has-flags    fidelity PASS but >=1 actionable visual flag remains.

Convergence (stop 'clean'): fidelity PASS AND actionable == 0. A light-effort figure that converges on its
single round stops 'light_single_pass'. Stagnation early-stop (researcher's 连续两轮没有实质改进 → 停止并说明原因):
the streak increments on every round that does NOT lower the best actionable floor seen among fidelity-PASS
rounds (a reverted/held round never lowers it); two in a row before the cap stops 'no_improvement'. The cap
stops 'max_rounds'.

The DESIGN-BRIEF redesign license (spec/figure-loop.md bindings DESIGN_BRIEF / REDESIGN_LICENSED) changes
NOTHING here: round_cap is a caller-supplied input (the caller passes REDESIGN_MAX_ROUNDS for a licensed
redesign), a brief-matching structural change is just a fidelity PASS, an off-brief one is just a HOLD, and
in a redesign flow round 1 IS the redesign — so the reduction below is license-agnostic by construction.

best-round: the LOWEST actionable count among the fidelity-PASS (shippable) rounds; ties resolve to the
LATEST round. If NO round both preserved the data (PASS) and produced a figure, do_no_harm is true and the
caller ships the ORIGINAL (shippedVersion 0) — figure mode keeps do-no-harm (unlike /polish sections).

── mode: "round" ──────────────────────────────────────────────────────────────
in : { mode, round, round_cap, effort ("light"|"normal"|"heavy"), no_improvement_rounds,
       history:[{fidelity_verdict:"PASS"|"HOLD"|"FAIL", actionable:<int>}, ...],   # prior rounds, in order
       current:{ fidelity_verdict:"PASS"|"HOLD"|"FAIL", actionable:<int> } }
out: { state, shippable, actionable, best_actionable_so_far, no_improvement_streak, stop, stop_reason }

── mode: "best" ───────────────────────────────────────────────────────────────
in : { mode, rounds:[{round, fidelity_verdict, actionable}, ...] }   # every round, in order
out: { best_round, best_actionable, do_no_harm }
"""
import json
import sys

INF = float("inf")


def _shippable(verdict):
    # A round is shippable iff the data was preserved (fidelity PASS). FAIL (drift) and HOLD (rescale held
    # for approval) are both do-no-harm reverts -> un-shippable (actionable ∞), recorded differently upstream.
    return verdict == "PASS"


def _effective_actionable(verdict, actionable):
    # ∞ (un-shippable) for a reverted round; else the caller's actionable count.
    return actionable if _shippable(verdict) else INF


def _streak_and_best(seq):
    """[[MECH]] reproduce runFigure's stagnation bookkeeping exactly: bestActionableSoFar starts at ∞; a
    fidelity-PASS round whose actionable is STRICTLY below it is progress (reset streak, lower the floor);
    every other round (a PASS round that does not lower it, or a reverted/held ∞ round) is a no-improvement
    round. Returns (best_so_far, streak) AFTER the final round in seq."""
    best_so_far, streak = INF, 0
    for r in seq:
        v = r.get("fidelity_verdict")
        act = r.get("actionable", 0)
        if _shippable(v) and act < best_so_far:
            best_so_far = act
            streak = 0
        else:
            streak += 1
    return best_so_far, streak


def run_round(data):
    round_no = data.get("round", 1)
    round_cap = data.get("round_cap", round_no)
    effort = data.get("effort", "normal")
    no_improve = data.get("no_improvement_rounds", 2)
    history = data.get("history", []) or []
    cur = data.get("current", {}) or {}

    verdict = cur.get("fidelity_verdict", "PASS")
    actionable = cur.get("actionable", 0)
    reverted = not _shippable(verdict)

    if reverted:
        state = "reverted"
    elif actionable == 0:
        state = "clean"
    else:
        state = "has-flags"

    seq = list(history) + [cur]
    best_so_far, streak = _streak_and_best(seq)

    converged = (not reverted) and actionable == 0
    stop, reason = False, None
    if converged:
        stop, reason = True, ("light_single_pass" if (round_no == 1 and effort == "light") else "clean")
    elif streak >= no_improve and round_no < round_cap:
        stop, reason = True, "no_improvement"
    elif round_no >= round_cap:
        stop, reason = True, "max_rounds"

    return {
        "state": state,
        "shippable": not reverted,
        "actionable": (None if reverted else actionable),   # None == ∞ (un-shippable) in JSON
        "best_actionable_so_far": (None if best_so_far == INF else best_so_far),
        "no_improvement_streak": streak,
        "stop": stop,
        "stop_reason": reason,
    }


def run_best(data):
    rounds = data.get("rounds", []) or []
    # shippable = fidelity-PASS rounds (finite actionable). Pick the MIN actionable; ties -> LATEST round
    # (iterate in order, replace on <=, exactly like runFigure's reduce). None shippable -> do-no-harm.
    best = None
    for r in rounds:
        if not _shippable(r.get("fidelity_verdict")):
            continue
        if best is None or r.get("actionable", INF) <= best.get("actionable", INF):
            best = r
    if best is None:
        return {"best_round": None, "best_actionable": None, "do_no_harm": True}
    return {"best_round": best.get("round"), "best_actionable": best.get("actionable"), "do_no_harm": False}


def main():
    data = json.load(sys.stdin)
    mode = data.get("mode", "round")
    out = run_best(data) if mode == "best" else run_round(data)
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
