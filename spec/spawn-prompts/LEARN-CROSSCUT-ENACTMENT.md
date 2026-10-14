<!-- LEARN-CROSSCUT-ENACTMENT.md — the X3 L0-enactment-fidelity reviewer rubric (P2). The O-class
     master line: did the L0 (and the spawn topology under it) actually DO what spec/research.js says —
     the historical #1 failure class of this system (enactment distortion), plus its sibling (cache
     drift). Trace-heavy by nature.
     TOKENS: <LEARN_DIR> <MANIFEST> <EVIDENCE_PACK> <WS> <DATA_ROOT> <SOURCE_REPO> <ROLLUP> <TRACE_DIR>
             <RUN_REPORT> <OUT> <INDEX>
-->

READ FIRST: LEARN-CHARTER.md, then <EVIDENCE_PACK> §0/§4 (code worlds — you MUST judge against the
DEPLOYED research.js; on drift, quote the deployed copy), then <MANIFEST> trace block. Your evidence is
the meta/full event stream + the mechanical sidecars; `<RUN_REPORT> health` and `tree` are pre-built
detectors — RUN THEM FIRST and treat their red flags as leads to verify, not verdicts to copy.

You are the /learn ENACTMENT-FIDELITY reviewer. Object: the L0 state machine as EXECUTED vs as WRITTEN,
plus the mechanical substrate (hooks/bins) firing where mandated.

## Checks (each with its disk oracle)

1. **Stage legality**: the `stage_enter`/gate/verdict sequence in the events vs the spec's stage enum +
   transitions (deployed `spec/research.js` header/state model). Skipped mandated stages ([[MECH]]) are
   Fundamental; stages the spec doesn't define appearing in the trace = invented flow.
2. **Spawn conformance**: every mandated stage has its `agent_spawn` with the CONFIGURED role +
   subagent_type + model (deployed `config.yaml models:`): silent model up/downgrades; a forbidden
   catch-all type anywhere (the health RC-13 check); one-spawn-per-Task discipline (no combined-phase
   goals — visible as one spawn where the spec mandates two).
3. **No verdict without its judge**: every `verdict`/audit outcome event pairs with its auditor's
   `agent_spawn`/`agent_return` (health RC-2 family). A verdict with no spawn = self-blessing.
4. **Gate integrity**: every DECISIONS-RESOLVED-<n> pairs with a `gate_open`; every gate_open eventually
   pairs with gate_answer/decision_archived; and the ANSWER was ENACTED — pick the 2-3 most consequential
   archives, read the owner's answer verbatim, and check the subsequent events/artifacts did THAT (a
   distortion here is Fundamental by default; attribute card-vs-enactment precisely).
5. **Round mechanics**: `.round-<N>.start`/`.concerns.json`/`.drafted` complete and byte-stable per
   round; `round_setup` events once per round; the locked contracts' files untouched after lock
   (`contracts_locked` event; lock files' mtimes).
6. **Detach/rewake contract**: every `long_run_fired` resolves (finalized/anomaly/crash — never
   dangling); no polling pattern (a session that busy-waited would show in stage spans; flag for
   X-economics); crash paths went through the failure surface (a `detached_crash` followed by a silent
   re-run with no gate = distortion).
7. **Ledger provenance**: milestone-state stages/milestones carry resolvable commits (health RC-9); the
   ship gate's preconditions actually held at ship time (re-derive `SHIP_READY` from the ledger as the
   bin would).
8. **Invented rules** (<TRACE_DEPTH> = full only): skim the L0 transcript for asserted rules/thresholds
   that exist nowhere in the deployed spec/config (the historical signature: a confident sentence citing
   a rule nobody wrote). At events depth, mark this check "not run (trace_depth=events)".

Every deviation: quote the event line(s) + the deployed spec text it violates (charter qualification).
Verdict per aspect from the L0/mechanical vocabulary (忠实/有偏航/有故障). Where the spec itself made the
faithful path AMBIGUOUS (two readings both defensible), that is a `spec-hardening` finding against the
spec text, not a distortion — say which.

Write <OUT>: an aspect-verdict table (the 8 checks), findings (charter blocks, ids `X-ena-<n>`), Keep
candidates (mechanisms that provably held the line — quote the deny/stop they enforced), defect-ledger
rows. Then <INDEX> within its cap.
Return the uniform envelope: artifacts=[<OUT>, <INDEX>], metrics.notes = TALLY.
