# Remediation — a run is sub-contract (G1), or it OOMs

Read this when a run missed the SCALE-CONTRACT (the L0 scale audit reports a gap) **or** a run OOMs. You **never
reduce the science** and you **never fix it one knob at a time.** Default assumption: your design was INCOMPLETE.

- **(a) Holistic up-scale-plan.** Produce an `UP-SCALE-PLAN.md` that brings EVERY deficient dimension up to the
  SCALE-CONTRACT in ONE step — the L0 scale audit returns the full gap set, not one item. You may spawn a Plan
  helper (per your spawn contract) to design it.
- **(b) Independent review gates the re-run.** An independent L0 reviewer rigor-reviews that plan (you do not
  bless your own plan); the re-run is gated on its PASS.
- **(c) OOM specifically.** Do NOT pre-shrink to dodge it — author at full contract scale, let the run FAIL
  loudly, then re-express the SAME full-scale science as multiple memory-bounded scripts run SERIALLY (partition
  seeds/grid across processes, tile the domain, checkpoint). Never lower a science value. Only if the irreducible
  minimal unit still OOMs is it an **S3** wall to surface (RETURN in `escalations[]`).

**Incremental knob-bumping is FORBIDDEN** (raise one dim, re-run, find the next gap, raise it, re-run …). Design
the full rigorous experiment ONCE.
