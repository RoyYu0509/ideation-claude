<!-- polish-cross-section-sweep.md — the read-only CROSS-SECTION CONSISTENCY sweep rubric (/polish Phase-2.9).
     SSOT for the ONE read-only reviewer that diagnoses cross-section inconsistencies only; its flags are
     then ROUTED per file to a per-file fix reviser by the orchestrator. Venue-NEUTRAL (no venue preamble —
     it judges internal consistency, not register). Extracted out of spec/polish.js (runCrossSectionSweep's
     diagnose goal-builder); the slim goal READS this file, substitutes the <TOKENS> below, appends the
     reviewer thinking block, and passes it as the reviewer goal. It returns SWEEP_SCHEMA (enforced at the
     call site).
     TOKENS the goal-builder substitutes (every one MUST be replaced before the goal ships):
       <MASTER>            the master/root manuscript file
       <CONTEXT_FILES>     all section files (comma-joined)
       <PLANNED_SECTIONS>  the planned sections (comma-joined); flags tag one of these or "master"
-->

Read the whole polished paper (master <MASTER> + all section files:
<CONTEXT_FILES>). Find cross-section inconsistencies only: terminology /
symbol drift, abbreviations not defined once before first use, and citation / cross-reference
wording that disagrees across sections. Do not re-review any single section's prose. Tag every
flag with the owning `section` (one of <PLANNED_SECTIONS>, or "master"). Return the schema.
