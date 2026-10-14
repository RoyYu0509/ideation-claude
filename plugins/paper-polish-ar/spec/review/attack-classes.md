<!-- review/attack-classes.md — the depth catalogue for the DEPTH MANDATE. A reviewer sweeps the venue
     rubric's axes for coverage, then picks the class here that best fits what it smelled and pursues that
     ONE thread until killed or grounded (verbatim quote + location — the grounding floor applies to every
     charge below). Curated from real failures this pipeline shipped past reviewers (W28 run et al.). -->

# Attack classes — where mediocre reviews stop and real ones start

**How to use**: these are hunting patterns, not a checklist. Do not tick through them — after your
coverage sweep, choose the one or two classes with the strongest scent and go DEEP. Tag the finding with
`attack_class`. Severity still calibrates by the venue's `scoring.md`.

## 1. True-by-construction (vacuity)
The headline result is guaranteed by the setup, not discovered by the work. Test: *would ANY correct
implementation of the cited theory have produced this number?* If yes, the number is a consistency check
wearing a result's clothes. (Shipped example: "coverage ≈ 90%" under split-conformal — Proposition-level
theory GUARANTEES ≈1−α for any correct implementation; the paper presented it as its headline finding.)
Hunt: trace the headline metric back to what pins it — theorem, calibration procedure, or the data itself.

## 2. Trivially-true-on-this-data
The metric is saturated because THIS dataset cannot discriminate, not because the method is good.
(Shipped example: tightness = 1.000 where only 2 of 50,844 test molecules had a true error above
threshold — nothing to be tight against.) Hunt: for every saturated/near-perfect number, compute what the
metric would read for a TRIVIAL baseline on the same data; if similar, the number is the dataset's
property, not the method's. Demand the discriminating regime or call the claim unsupported.

## 3. Discriminative-power failure (explained-away negative)
The one experiment that could show the method is USEFUL fails — and the text explains the failure away
instead of owning it. (Shipped example: usefulness AUROC = 0.37 — BELOW random — narrated as "the model is
too accurate to measure discrimination".) Below-random is a finding about the method, not the metric.
Hunt: find the experiment whose SUCCESS the abstract needs; check whether its actual numbers support the
narrated conclusion or merely coexist with it.

## 4. Spin (abstract vs. delivered)
The abstract/title/intro claim a stronger thing than the results section delivers — scope, certainty, or
mechanism inflated in exactly the places casual readers and tired reviewers look. (Shipped example:
"almost nothing left to certify" packaged as "the certificate certifies almost all already-accurate
molecules"; a conformal wrapper titled as an "a-priori error bound".) Hunt: put the abstract's every
claim-bearing sentence side by side with the strongest evidence for it; quote both; flag every gap.
Terminology counts: a method NAME that promises more than the mechanism delivers is spin with a `referent:
definition_identity` — scoping language is the fix, never renaming the contribution (do_not_touch).

## 5. Claim↔experiment validity (the redesign class)
The experiment does not test its own claim: a linear operator under a nonlinear claim, a same-model
"baseline" that is not a real comparator, a metric that cannot move whatever the truth is, adding data
making results WORSE unremarked. This is `remediation_type: missing_experiment` with `fix_kind:
needs_author` and — in-loop — ALWAYS a redesign export (`needs: experiment`), never a spec-wording fix: words can
NEVER fix a broken experiment.

## 6. Hollow contribution (the reward-hack dual)
Is the headline outcome a real positive result — or is it HOLLOW: no working method actually produced, a
circular/trivial claim, a "could not get it working" write-up dressed as a finding, an underpowered
negative with no hypothesis at stake? An honest-but-EMPTY deliverable is a reject — the dual of
overclaiming; do not wave it through because it is honest.

**A negative that contradicts the central novelty claim is not a contribution either.** If the named
central bet died with evidence, the DIRECTION is dead and the standing policy is to abandon it — that is
a reject-class finding, not a deliverable. Do not acquit it on the grounds that the work was rigorous or
the reporting honest; rigor is what makes the refutation trustworthy, not what makes it publishable. A
negative on a peripheral/technical criterion is a different thing: record it as a steering fact, never as
the headline.

## 7. Circular evaluation
The gate/threshold/metric was tuned on the same data it certifies, a "sanity check" that passes by
construction, a near-degenerate threshold doing all the work. Hunt: for every pass/fail criterion, ask
where its threshold came from and what would have happened to the paper had it been set before seeing the
data.

## 8. Novelty / competitor (reskin)
The contribution is an existing method renamed, or the DIRECT competitor is absent from the comparisons.
You hold the investigation license here: search the literature, NAME the competitor (verbatim title), and
state what comparison is missing. Never invent a citation; a missing reference is `needs_author` with
search keywords.

## 9. Theory–prose mismatch
The prose asserts more than the math: a sketch called a proof, an assumption dropped between statement and
use, a bound derived under conditions the experiments violate, "we prove" where the object is never used
as proven (e.g. a perturbation bound never actually applied as a deterministic bound). Re-derive the
smallest load-bearing step yourself (scratch work is licensed) before charging.

## Guard: the false-rejection tax
Every class above loses its force if the demanded item actually EXISTS in the paper. Before asserting
"missing X" or "the method is Y, not Z": open the typeset figures, tables, and appendix and look. The
synthesis seat dismisses present-but-missed demands — a reviewer who racks them up gets its serious
findings discounted wholesale.
