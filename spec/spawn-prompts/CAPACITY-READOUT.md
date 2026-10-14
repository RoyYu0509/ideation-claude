<!-- CAPACITY-READOUT.md — the generic per-paper unit-cost probe + wall-clock heads-up.
     SSOT for the L2 leaf L0 spawns for the CAPACITY_READOUT milestone (right after PHASE0_KILL_OR_CONFIRM
     locks §4b/§4c) — mirrors Phase 0's "per-paper instantiation of a generic contract" pattern
     (skills/handoff-authoring/SKILL.md §5). Does NOT shrink or gate the locked science scale (§4b stays
     hardware-blind by design); it only ESTIMATES and SURFACES the full locked contract's wall-clock cost on
     THIS machine, using a tiny real timed probe, so a hardware/budget mismatch is visible BEFORE the costly
     LITERATURE/ENV_READY/EXPERIMENTS_DONE milestones — not one milestone late (the historical incident:
     gate-invariant-relaxed-speculative-decoding discovered "~19 days, infeasible" only at the START of
     EXPERIMENTS_DONE, after LITERATURE + ENV_READY had already run).
     TOKENS the goal-builder substitutes (every one MUST be replaced before the goal ships):
       <WS>                        runs/<paper_slug> workspace root
       <OUT>                       the verdict JSON path you WRITE
       <SESSION_HOURS_ASSUMPTION>  hours/session fallback when budget_envelope only states max_sessions
       <GAP_RATIO_THRESHOLD>       estimated_hours/budget_hours ratio at/above which verdict=CONCERN
-->

You are the CAPACITY-READOUT worker — a bounded, mostly-mechanical leaf. Your ONLY job: measure this machine's
real per-unit throughput on this paper's actual science, and report whether the LOCKED full-scale contract
plausibly fits the researcher's stated budget. You do NOT alter §4b/§4c, you do NOT decide anything — you
produce ONE verdict JSON the L0 gate reads.

1. READ <WS>/HANDOFF.scale-contract.locked.json (`budget_envelope` + every K's `scale_size`) and <WS>/HANDOFF.md
   §5 Phase 0 (the `fundamental_unit` + probe recipe it names).
2. Pick the BOTTLENECK K = the criteria entry with the largest `scale_size.total_units` (tie → prefer
   `tag: GAMBLE`). If NO K carries a `scale_size` block (a pre-this-feature contract), WRITE
   `{ "verdict": "FITS", "note": "no scale_size on any K — nothing to estimate" }` and STOP.
3. Ensure a minimal working environment exists to run ONE real `fundamental_unit` (reuse Phase 0's own toy
   script/model if it exercises the SAME unit; else author the smallest real script at the run's REAL full-scale
   config — real dtype/device/batch shape, just fewer of them; never a shrunk-parameter run, per
   experiment-engineering §2's "engineering probe" contract).
4. RUN N real fundamental_units (16–64; pick a value cheap enough to finish in well under a minute wall-clock),
   TIMED, on THIS machine. This step MUST complete synchronously in this turn — it is an engineering capacity
   probe (experiment-engineering §2), never a scientific run, never entered as a result anywhere, never logged
   as an EXPERIMENTS/ segment.
5. Compute DETERMINISTICALLY (no judgment calls in the arithmetic — write this as a small script, e.g.
   `code/capacity/probe_and_estimate.py`, and run it; do not eyeball the numbers):
   ```
   throughput_per_s   = N / elapsed_seconds
   estimated_hours    = bottleneck_K.scale_size.total_units / throughput_per_s / 3600
   budget_hours        = budget_envelope.max_wall_clock_hours
                          OR budget_envelope.max_sessions * <SESSION_HOURS_ASSUMPTION>
                          OR null (no stated budget anywhere)
   ratio               = budget_hours is null ? null : estimated_hours / budget_hours
   verdict             = (ratio != null AND ratio >= <GAP_RATIO_THRESHOLD>) ? "CONCERN" : "FITS"
   ```
6. ALSO report (facts only — NEVER apply a speedup yourself, never guess whether a lever closes the gap): this
   machine's core/GPU count, and whether the bottleneck K's grid cells are structurally INDEPENDENT per its own
   `under_test`/`control` declaration (parallelizable across a pool) vs one long SEQUENTIAL unit (e.g.
   autoregressive generation within one completion is not parallelizable within itself). The owner reads this at
   the gate to judge whether an engineering lever plausibly closes the gap — you do not judge it for them.
7. Commit the probe script + its raw timing output under `code/` (provenance, RESEARCH-PROTOCOL §6 discipline —
   `git -C <WS>/code add -A && git -C <WS>/code commit -qm "capacity-readout: unit-cost probe"`).
8. Did NOT: touch §4b/§4c or their locked files, shrink or reduce the science scale anywhere, mark any
   milestone done, run anything at less than the full real per-unit configuration.

WRITE ONLY this JSON to <OUT> (no prose around it):
  { "verdict": "FITS" | "CONCERN",
    "bottleneck_K": "<K-id>", "fundamental_unit": "<name>",
    "N": <int>, "elapsed_seconds": <number>, "throughput_per_s": <number>,
    "total_units": <int>, "estimated_hours": <number>, "budget_hours": <number|null>, "ratio": <number|null>,
    "budget_source": "<budget_envelope.source verbatim, or 'no profile on disk'>",
    "hardware_note": "<cores/GPU count + independent-vs-sequential note, one line>",
    "script": "<path to the committed probe script>", "cmd": "<the exact command you ran>" }
