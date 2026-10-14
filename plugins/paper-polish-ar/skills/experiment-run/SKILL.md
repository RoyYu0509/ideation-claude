---
name: experiment-run
description: How to run a /review supplementary experiment locally at REAL full scale (no smoke), with tiering and fire-and-asyncRewake. Loaded by name by research-rescue and experiment-engineering.
user-invocable: false
---

# experiment-run — run it locally, at FULL scale, never block the session

The execution backend is **local Bash in the experiment repo directory**. Run all commands directly via
the Bash tool — no SSH. `cd` to `experimentRepo` first, or use absolute paths.

## 1. Environment readiness (once per repo per session; cache it)

Before any run, confirm locally: `command -v julia` / `julia --version` (repos pin a version);
`command -v python3`; `Project.toml` + `Manifest.toml` present; deps instantiated
(`julia --project=. -e 'using Pkg; Pkg.status()'` — if it errors "not installed", you need
`Pkg.instantiate()`, which can take minutes + network, so **budget it as a timed step**); the Python
plotting deps (`python3 -c 'import ...'`); and the input data (datasets pulled by the code
auto-download/cache; external/PI datasets may be absent → escalate to the author). If `julia`/`python3`
is missing or instantiate needs an absent proxy/network → **askUser, do not flail**.

## 2. Run the REAL configuration — no smoke, no scaled-down

Run only the **real, full configuration** the approved plan specifies — the actual epochs / seeds / grid
/ problem size. **Never** run a smoke, a "quick" reduced-scale proxy, or a toy version and then reason
from its result: a scaled-down run produces a *misleading* number (a too-short PINN looks like "no
heteroskedasticity"; a 1-seed run looks like "no effect"), and that false conclusion is exactly the
failure this phase exists to prevent. There is no separate "does it compile" step either — just run the
real thing; **if it crashes, fix the code and rerun the full configuration** (a crash fails fast and
cheap, usually at import/setup).

**Make the run hard to fake.** Tee the full stdout to a log, and ensure the experiment's own
**discriminative** sanity self-check runs and prints into that log — a cross-check that an independent
computation agrees (e.g. "SP residual matches QR to ~1e-11"), NOT a field-presence check. The
independent run-auditor re-reads that log; a vacuous sanity is treated as no sanity.

**Reproduce-before-compare (the verify run's sanity).** The only experiments run here are
`updates_existing` verifies (an experiment that needs NEW paper content is exported to the handoff, not run
— see below). So the discriminative sanity IS reproducing the paper: recompute the paper's existing
reported number (the plan's `reproduce_target`) with the paper's OWN metric definition/config and print
got-vs-paper + whether it is within tolerance into the log. If it does **not** reproduce, report that in
`sanity_check` and STOP — do **not** tune the config to hit the paper's number, do **not** swap. A
non-reproduction is a finding about the paper that the orchestrator surfaces, not a number to reconcile.

### New-exhibit work is exported, not run here

If a result would need a **new** table row, figure curve, or section, it is `new_exhibit`: `/review` does
not run or author it — the experimenter rendered it into `HANDOFF-<paper>.md` for the author to run and
integrate in a separate session. You will not be asked to author a new plot/figure in this phase; verify
runs only regenerate an EXISTING figure by re-running its plot script.

## 3. Tiering — short runs yourself, long runs handed to the orchestrator

> **SCOPE: standalone `/review-experiment` ONLY.** In the auto-research loop this section does NOT
> apply: EVERY science run fires DETACHED via `exp_ledger.py run-detach` — there is no "short ⇒ run it
> yourself" tier (`experiment-protocol.md` §4 / `agents/producing-worker.md` own that discipline).
> Callers no longer restate this; the scoping lives here, at the source.

Classify the run from cheap signals (a `*.slurm` file's `--time`/`--mem`, the docs' recorded durations,
the problem size — bias to the higher tier near a boundary, and trust a recorded duration over an
extrapolation):

- **Short (tier A/B, ≤ ~8 min)**: run it **yourself now** with Bash, at full scale; set `ran_self=true`
  and report the `stdout_log` path + the products written. The orchestrator records the run post-hoc
  from disk (`exp_ledger.py record`) so the provenance is minted outside your transcript.
- **Long (tier C/D, minutes → hours → days)**: do **not** run it. Set `ran_self=false` and return the
  EXACT full-scale `real_run_cmd` (a local Bash command from the repo root). The **orchestrator** fires
  it DETACHED (`exp_ledger.py run-detach`: a `start_new_session` background process whose PID is appended
  to `.polish/.bg-pids`) and ENDS THE TURN. There is **no HPC hand-off** — a `sbatch`/multi-day job still
  runs here; just report the long tier so the orchestrator detaches it.

If you discover mid-run that the approved plan is wrong (a new experiment, a changed config/scale, a
different design is needed), STOP and return `out_of_plan_change` — never silently run something the
human did not approve; the orchestrator re-surfaces the plan.

### The fire-and-asyncRewake discipline (NEVER poll)

> **Waiting is the shell's job; the re-wake is `exit 2`'s job; responding is yours. Keep them separate.**

Once a long run is fired detached, **do not** check on it — no `while`/`sleep` loop, no repeated
`test -f results/XX.json`, no `tail -f`, no Monitor, no ScheduleWakeup. Polling from inside the agent
loop burns tokens every iteration (it has cost 400k+ tokens before) and is forbidden. Instead the
session ENDS; the `Stop` hook `hooks/rewake-when-done.sh` (`asyncRewake: true`) OS-waits every PID in
`.polish/.bg-pids` — a pure shell wait that costs zero tokens — and `exit 2` re-wakes the session when
they finish. On re-wake the orchestrator calls `exp_ledger.py finalize` to capture the result, then
audits and writes it back. (A crash still "finishes" the PID, so the re-wake fires either way; finalize
records the non-zero exit code and the auditor fails it — silence never passes as success.)

## 4. Provenance boundary (do not cross it)

You run the real experiment; you do **not** certify it. The number's proof is minted outside your
transcript — for a short run the orchestrator records the after-state + your tee'd stdout from disk
(`exp_ledger.py record`); for a detached long run it stamps the before-state at `run-detach` and the
products/numbers at `finalize`. Either way the **independent run-auditor** re-derives every fact from
disk (number-in-file, git-sha-changed, the stdout log + the discriminative sanity) and only its PASS
lets a number reach the paper. You may regenerate a figure by running its `plot_*.py` (a Bash run writes
the figure file directly — produced, not hand-edited). **Never** create a results/figure file with
Edit/Write; if you cannot produce a value by executing code, return failure, not a hand-written number.
