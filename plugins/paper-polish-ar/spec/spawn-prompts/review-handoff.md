<!-- review-handoff.md — spawn-prompt for /review's HANDOFF-doc renderer (the REVIEW OWNER spawns the
     experimenter role with this rubric; see spec/review/output-contract.md "HANDOFF export" row).
     The HANDOFF mode of the experimenter shell reads this and renders the WHOLE HANDOFF-<paper>.md.
     TOKENS substituted by the goal-builder:
       <TARGET_VENUE>        — VENUE.label
       <EXPERIMENT_DEMANDS>  — JSON array of the exported experiment-demands (each carries the reviewer
                               concern + the paper claim it targets)
     Appended at runtime by the goal (do NOT duplicate here): the PAPER MODEL preamble, and the
     experimenter thinking directive. -->

# Render the research HANDOFF (HANDOFF mode)

You are rendering a research HANDOFF in HANDOFF mode. Produce the COMPLETE `HANDOFF-<paper>.md` — a portable
work order a FRESH autonomous-research session (Claude Code / Codex) will use to DESIGN, run, and integrate
these experiments into the paper. /review will NOT run them. Retrieve the `experiment-process` skill. Do NOT
run anything and do NOT edit the paper or any code — return ONLY the markdown (HANDOFF_DOC_SCHEMA).

The executing session reads `REVIEW-EXPERIMENT-PROTOCOL.md` (shipped alongside) as its operating constitution, then
this file. Structure: a short RUN HEADER, then one SECTION per experiment-demand.

## RUN HEADER

One paragraph of paper context from the paper model (problem / gap / main method / primary contribution /
target venue = `<TARGET_VENUE>`); a pointer to `REVIEW-EXPERIMENT-PROTOCOL.md`; and a REUSE, DO NOT REIMPLEMENT note —
the executor must REUSE the paper's OWN metric/data-generator code by import/call (a divergent
re-implementation yields a real-looking WRONG number); have the executor locate the canonical code in the
repo before running.

## PER EXPERIMENT-DEMAND

Each carries the reviewer concern + the paper claim it targets:

- **CORE HYPOTHESIS:** the paper claim under review + what an experiment here would establish.
- **KILL / FALSIFICATION CRITERIA:** the reviewer's adversarial concern, stated as "if the experiment shows
  X, the claim is falsified/weakened — report it honestly, do NOT bury it". If it adds a competing baseline,
  state plainly that a comparable or better baseline is a valid, must-report outcome.
- **WHAT TO RUN:** the executing session DESIGNS the experiment from the reviewer demand + the AC's
  proposed_fix + the paper location below — give it the concrete starting point (which claim, which
  section/figure/table, what the reviewer is asking for), then let it design the full config there.
- **INTEGRATION TARGET:** where the result should go (which table/figure/section) and what new content to add
  so it is integrated coherently, never a bolt-on. Every new exhibit needs a home in the BODY (a paragraph
  that argues it) — or an APPENDIX subsection with a one-line body reference. Discussion goes in prose, NEVER
  dumped into a figure caption.
- **REPRODUCE-FIRST (hard gate):** if the experiment compares against any EXISTING paper number, the executor
  MUST reproduce that number FIRST with the paper's own code/metric within tolerance before computing
  anything new; if it does not reproduce, STOP and report — do NOT proceed to compare or write back.
- **DISCRIMINATIVE SANITY:** a hard-to-forge self-check the run must print (recompute a key quantity an
  INDEPENDENT way and assert agreement to a tight tolerance) so the number is provably from a real run.

End with a per-run DEFINITION OF DONE (products on disk; honest holds/comparable/contradicts verdict vs the
kill criteria; coherent integration if it holds, or claim softened/dropped if it does not).

## EXPERIMENT-DEMANDS

<EXPERIMENT_DEMANDS>
