<!-- polish-abstract-candidates.md — the title+abstract REVISE-AND-SELECT candidate-generation rubric (/polish).
     SSOT for the reviser that runs LAST (after the body is final) and emits N MINIMAL revisions of the
     EXISTING title+abstract plus the original as a first-class baseline candidate (第一刀 do-no-harm).
     Extracted out of spec/polish.js (runAbstractSection's candidate-generation goal-builder); the slim
     goal READS this file, substitutes the <TOKENS> below, appends the venue preamble + the reviser
     thinking block, and passes it as the reviser goal. It returns ABSTRACT_CANDIDATES_SCHEMA (enforced
     at the call site) and does NOT commit (the orchestrator scores, then a separate reviser writes the winner).
     TOKENS the goal-builder substitutes (every one MUST be replaced before the goal ships):
       <FILE>           the abstract-body file to read (the title lives in <MASTER>'s \title{...})
       <MASTER>         the master/root manuscript file (holds \title{...})
       <CONTEXT_FILES>  the whole paper (comma-joined), read for context
       <N>              how many candidate revisions to produce
       <ARC_NOTES>      keynote arc notes to honor, or "(none)"
-->

You are the reviser polishing the title + abstract of the paper, LAST, after the body is final,
so the abstract condenses the finished paper. The abstract body lives in <FILE>; the title
lives in the master <MASTER> (\title{...}). Read the WHOLE paper (<CONTEXT_FILES>)
for context. Retrieve polish-prose + house-style + section-abstract.
Make the MINIMAL NECESSARY REVISION of the EXISTING title + abstract — do NOT write a fresh
abstract from scratch. Produce <N> candidate revisions; each must START from the current
abstract and change ONLY what is defective (an AI tell, a flat/uninformative sentence, a broken
funnel turn). KEEP every sentence that already reads well; do NOT replace the original opening
unless the opening itself is the defect. If the current abstract has no defect, the correct
candidate is the original unchanged.
Keynote arc notes to honor: <ARC_NOTES>
Also return the original title + abstract verbatim as the baseline (it is a first-class candidate).
Return the schema; do not commit yet.
