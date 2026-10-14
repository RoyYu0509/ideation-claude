# Transient environment failure — capture hygiene (anti-self-poisoning)

Read this when a run **DIED** (crashed, was killed, never finalized) rather than **completed and measured
something**. The single rule this file exists for: **a transient environment failure must never solidify into
persistent memory** — not as a weakened claim, not as a "falsified idea", not as a /learn hypothesis, not as a
capability-negative sentence. Store *the fix that worked*, never *"X can't do Y"*.

**The dividing test is ACTION, not signature** (same philosophy as `operational-first.md`'s G1–G3):
- **transient** = the identical command, code, and config would succeed on a plain re-run — the cause lived in
  the environment (API overload, machine sleep, network, disk, resource contention).
- **systematic** = the identical re-run reproduces the failure — the cause lives in the code or the science,
  and the normal failure routing (`operational-first.md`, `remediation.md`, S1–S10) owns it.

**Deterministic signatures** (the mechanical twin is `bin/classify_crash.py` — regex changes there and here
move together). Cause closed-set: `env_transient | oom | code | unknown`.
- `env_transient`: `429` / `529` / `overloaded` / `rate limit`; PID dead with **no exitcode file** (laptop
  sleep / external kill); `connection refused|reset` / `timed out` / `temporarily unavailable`;
  `no space left on device`.
- `oom` — **never classified transient OR systematic by signature alone.** `CUDA out of memory` /
  `MemoryError` / `OOMKilled` yields `oom` = *awaiting adjudication*: re-run identically ONCE. Passes ⇒ it
  was contention (transient — keep nothing beyond the tagged crash line + its RESOLVED note). OOMs again ⇒ a
  genuine capacity wall (systematic) — the existing route stands unchanged: partition, never down-scale
  (`remediation.md`), smallest indivisible unit still OOM ⇒ S3.
- `code`: a traceback / assertion / syntax / name error — normal diagnosis, never suppressed by this file.
- `unknown`: no signature matched — treat as systematic for diagnosis, but never invent a science meaning.

**The four capture anti-patterns — what must NOT be persisted** (adapted from ARIS `capture-antipatterns.md`):
1. **Env-specific failure** (missing module, command not found, bad path): store the fix / the dependency /
   the correct config. Never store it as a fact about the science or about a component's capability.
2. **Transient error** (the signatures above): a self-resolving event. Its ONLY legal durable traces are the
   `[cause:env_transient]`-tagged crash line and the RESOLVED note that closes it; the only legal *learning*
   is a retry/backoff/mechanism improvement that actually worked (the machine-improvement lane).
3. **Negative capability claim** ("X can't do Y") sourced from a failure: forbidden on every persistent
   surface (FAILURES/RESEARCH_LOG conclusions, the dossier, FINDINGS, /learn hypotheses). Store "how to make
   X do Y", or nothing.
4. **Single-instance narrative**: one transient death never grounds a class-level verdict (a viability call,
   a quality-ledger trend, an ideation hindsight label). A class-level rule needs the quality ledger's ≥3
   same-direction points, and those points must be **cause-homogeneous**.

**Disposition = discard-by-default.** No quarantine store, no TTL. Append-only logs cannot be unwritten, so
"discard" here means: the crash line carries its `[cause:*]` tag, a successful re-run appends a RESOLVED note
pairing it closed, and every downstream judgment surface (dossier, rescue, viability, /learn) is bound to
treat tagged-transient events as machine evidence only — citing one as SCIENCE evidence is auto-invalid.

**The negative space — what this file must never be used to suppress:**
- A **completed, full-scale, measured negative outcome** (it has quantitative lines and AUDITED-VALUES keys —
  a transient death can produce neither) stays a real measurement that must be recorded and routed by
  `operational-first.md`; nothing here touches it. (Recording it is not the same as DELIVERING it — a negative
  that contradicts the spec's novelty claim is still an abandon signal, not a contribution.)
- A **deterministic re-OOM** is a real capacity wall: partition / S3 routing is untouched.
- A **code bug** (`cause:code`) gets normal diagnosis and its FAILURES line; only capability-negative
  *conclusions* are banned, not the record of the bug and its fix.
- **Machine-resilience learning is legal**: "add 529 backoff to spawnAgent" is exactly the workaround lane —
  a /learn finding or hypothesis about the MACHINE may cite transient events as its evidence.
- A **died run is never a result**: it produces NO `result.md`, is never "honestly recorded as a negative
  result", and never enters G1 — falsification requires a COMPLETED run's measured numbers.
