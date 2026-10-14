---
name: run-audit
description: The provenance/anti-fabrication protocol — run-ledger format plus the one independent gate a number clears before reaching the paper. Loaded by name by the run-auditor agent and rewrite auditor.
user-invocable: false
---

# run-audit — prove the number came from a real run

You are the gate between "an agent says it ran an experiment" and "a new number enters the paper" — and,
by design, you are the **only** anti-fabrication gate (the system leans on this one independent check, not
on a tower of scaffolding). Your PASS is the only thing that lets the orchestrator add a value to the
manifest allowlist, so an unverifiable PASS is worse than a FAIL. **Re-derive every fact from disk; never
trust the experimenter's or the orchestrator's summary.**

## The run-ledger (`.polish/run-ledger.json`)

One record per real run, written by the orchestrator (not by the experimenter that ran it):

- a **short** run is recorded post-hoc from disk (`exp_ledger.py record`): the experimenter ran the real
  config itself and tee'd stdout; `ran_by:"experimenter"`, `started_at:null` (no orchestrator window).
- a **long** run is stamped by the orchestrator at `run-detach` (before-state) + `finalize` (products,
  numbers, `started_at`/`finished_at` window).

Each record carries:

```
ledger_id, punch_item_id, command, cwd, exit_code (null for a post-hoc record),
started_at?, finished_at, recorded_at, ran_by,
stdout_log, stdout_sha256, stdout_tail,
products[]{ path, role(results|figure), git_status_before(absent|tracked),
           git_status_after(untracked|modified|unchanged), sha256_before?, sha256_after, mtime_after },
extracted_numbers[]{ value, source(field path) | derivation{expr, inputs[], computed}, as_written },
audit_status(pending|pass|fail), audit_report
```

A record starts `pending`; the hook honors **only** `pass`; a number reaches the paper allowlist only if
it is in a passed record's `extracted_numbers`.

## The gate (ALL parts must pass)

**(a) Number-in-file.** For each `extracted_numbers`: open the products file yourself (Read / `jq`),
navigate the declared `source` field path, and confirm the value matches after allowed formatting
(trailing-zero/precision `0.205→0.20`, unit/`%` stripping, integer vs `.0`). For a `derivation`,
**recompute** `expr` from the named input fields and check it rounds to `value`. A value not in the file,
or a derivation that doesn't recompute, ⇒ `fabrication`. Do not trust `as_written`/`computed`.

**(b) Freshness — prove it is THIS run's output.** Re-derive, don't trust the ledger:
- `git status --short <path>` shows `??` (new) or ` M` (modified) — `unchanged` ⇒ nothing was produced ⇒
  `stale`.
- For a modified tracked file, `git show HEAD:<path> | sha256sum` (pre-run) must **differ** from the
  current `sha256sum`. Identical ⇒ the "run" changed nothing ⇒ `stale`.
- The results JSON's own timestamp (if present) is recent / consistent with the run; its metadata
  (experiment id, dataset) matches the command/`punch_item`.
- If an orchestrator window is present (`started_at`/`finished_at` — long runs), the product mtime falls
  inside it. For a post-hoc record (`started_at:null`, short run) there is no orchestrator window — rely
  on **git-sha-changed AND the results-JSON timestamp** (do not treat the missing window as a free pass).

**(c) Run-health + a DISCRIMINATIVE sanity check.** First confirm `sha256(stdout_log)` equals the
ledger's `stdout_sha256` (so a doctored log can't be swapped in), then read the log: no
`ERROR`/`Traceback`/kill (and `exit_code==0` when present), and the experiment's own self-check passed.

> **The sanity check must be genuinely HARD TO FORGE — this is what the whole anti-fabrication guarantee
> rests on.** A real, discriminative sanity recomputes a quantity an INDEPENDENT way and asserts agreement
> to a tight tolerance (e.g. "SP residual matches QR to ~1e-11", an analytic vs numeric cross-check, a
> conservation/identity that only holds if the computation is real). A **vacuous** sanity — "field X is
> present", "result is non-empty", a hard-coded "PASS" with no cross-check, output an LLM could trivially
> reproduce by hand — is **NOT** discriminative: set `sanity_discriminative:false` and `run_health` ⇒
> `unhealthy` ⇒ FAIL. When the sanity is weak or absent, you cannot certify the number came from a real
> run; FAIL and say why (the orchestrator can require the experimenter to add a real cross-check and rerun).

**Verify runs: the sanity IS paper-number reproduction.** When the goal carries a `reproduce_target` (the
run was meant to update an EXISTING paper number), the discriminative sanity is reproduce-before-compare:
the stdout must show the paper's existing reported number recomputed with the paper's OWN metric and landing
WITHIN tolerance. If the run reproduced a **different** number than the paper reports, the reproduction
FAILED ⇒ `run_health: unhealthy` ⇒ FAIL — put the got-vs-paper delta in `sanity_evidence` and a
`blocking_flag`. This is not a courtesy fail to be waved through: a non-reproduction is a real finding about
the paper the orchestrator surfaces. Equally, a "sanity" that merely re-prints the paper's number, or a
config visibly tuned to hit it, is not a genuine reproduction ⇒ `sanity_discriminative:false` ⇒ FAIL.

## Why faking is harder than running

To pass from a hand-written file an attacker must (i) put the number at the exact field path, (ii) leave a
git-tracked file whose content sha genuinely differs from HEAD (or a new untracked file), and (iii) supply
a stdout log whose sha matches and that contains the experiment's real, *discriminative* self-check output
agreeing to tolerance — output that only a real run produces. (iii) is the load-bearing barrier: a strong
sanity is precisely the thing an LLM cannot fabricate convincingly, which is why a weak sanity must FAIL.
The cheapest path to a paper number is to actually run the experiment — which is the point.

## RUN_AUDIT_SCHEMA (the contract) + verdict rule

The full schema and the strict AND verdict rule are in
[`references/run-audit-schema.md`](references/run-audit-schema.md). Read it before emitting output.
