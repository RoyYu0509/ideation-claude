# Gate integrity — a gate told you the science didn't hold and you want to change it

Read this when a gate / sanity / pre-registered criterion FAILed (it told you the science did not hold) and you
are tempted to change it. A G3 fix's scope is a **producing-artifact**, NEVER an **audit-artifact**. You may NOT
rewrite the gate so the run passes — that is moving the goalpost (e.g. a single-seed gate rewritten into a
pass-by-construction ladder, then self-certified by firing the downstream waves).

Only two honest moves:
- **(i) The FAIL is about the experiment** → fix the experiment and re-run the **unchanged** gate.
- **(ii) You genuinely believe the gate is wrong** → you may **PROPOSE** the change (edit it AND log the reason
  in RESEARCH_LOG.md), but you do NOT **DISPOSE** it.

At the next wave boundary, L0's independent in-round auditor re-derives every registered audit-artifact's sha; a
changed one is judged legitimate-fix vs goalpost-move, and a goalpost-move HARD-BLOCKS the next wave and surfaces
to the owner. **PROPOSE ≠ DISPOSE** — you are never the one who blesses a change to your own gate. And a central
`[GAMBLE]` FAIL is routed via the S1 escalation (`failure/operational-first.md`), NEVER re-anchored by the worker
authoring its own `DECISIONS-RESOLVED-*.md`, editing a `HANDOFF.*.locked.json`, or swapping the headline metric
into a pass — that is a goalpost-move, not an honest outcome.

And a gate that decides pass/fail on a STOCHASTIC quantity must itself honor the §4b seed floor: a **single-seed
gate**'s FAIL is noise, not a result — run ≥ the seed floor and judge the cross-seed outcome, never "fix" the
FAIL by editing the gate.

This also cuts the other way, at authoring time, not just at rewrite time: don't wire a condition into the
gating boolean that HANDOFF never pre-registered, even if you label it "report-only" — the code's actual gating
behavior is what gets judged, a comment doesn't change it. L0's independent auditor reviews a `gate`/`criterion`
artifact's FIRST content too (§4), so an ungrounded condition baked in from birth gets caught even if you never
touch the file again — see the asset's WHY YOU EXIST #2 for the real incident this closes.
