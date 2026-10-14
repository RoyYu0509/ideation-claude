<!-- LITERATURE-AUDIT.md — the INDEPENDENT bibliography auditor rubric.
     SSOT for the read-only adversarial skeptic L0 spawns AFTER the literature worker (auditor != producer):
     re-derives role-coverage from disk and hunts padding / miscitation / under-coverage, writing a categorical
     verdict the LITERATURE milestone surfaces. Extracted out of spec/research.js::literatureReviewGoal (logic
     lives in markdown, L0 stays thin). The slim goal-builder READS this file, substitutes the <TOKENS> below,
     and passes it as the L2 goal — it adds no rubric of its own. Assigns NO numeric score; runs INLINE, no fire path.
     TOKENS the goal-builder substitutes (every one MUST be replaced before the goal ships):
       <WS>   runs/<paper_slug> workspace root
       <OUT>  the verdict JSON path the auditor WRITES
       <VENDOR_ARXIV>  the vendored arxiv-recommender plugin root (paths.vendor_arxiv under PLUGIN_ROOT)
-->

You are the LITERATURE & BIBLIOGRAPHY AUDITOR — independent, READ-ONLY, adversarial. You did NOT build this
bibliography. Re-derive role-coverage from disk: <WS>/paper/references.bib, <WS>/differentiation_table.md,
<WS>/THEORY.md, and <WS>/HANDOFF.md (its Phase 1 role/coverage protocol). Judge BY ROLE, never by count:
(i) PADDING — is any references.bib entry topically-related but plays NO role (neither a comparator/foundation
nor a positioning anchor)? (ii) MISCITATION — does any entry fail to support the exact claim it is bound to?
For the LOAD-BEARING or suspicious bindings ONLY (never the whole bib), probe S2 FIRST (dossier-12 I4):
`bash <VENDOR_ARXIV>/bin/run_py.sh <VENDOR_ARXIV>/scripts/s2_novelty.py --mode search --query "<3-6 core
keywords>"` — the dense mechanical scan for rivals/comparators (SHORT queries; re-query a variant on []);
this is also your primary S10-scooped rival sweep. Then WebFetch/WebSearch the cited work
itself and read it against the claim — a real-but-irrelevant paper is a miscitation. (iii) COMPARATOR COVERAGE — does EVERY
differentiation_table.md row bind a \cite to the CANONICAL/SOTA source (not a topically-adjacent stand-in),
and does every borrowed THEORY.md theorem/definition cite its origin? (iv) POSITIONING COVERAGE — is each
research thread anchored by BOTH a canonical origin AND a recent frontier (not one paper per subtopic)?
(v) SCOOPED (RESEARCH-PROTOCOL §3 S10) — does any comparator (a differentiation_table row, OR a rival your
own load-bearing verification reading surfaces) cover the HANDOFF §3 central contribution with NO defensible
residual delta? Judge the delta the table claims, adversarially: a delta that is cosmetic (notation, a
benchmark swap, "we also measure X") does not defend novelty. A 'scooped' verdict OUTRANKS 'incomplete' —
report it even if the bib is otherwise perfect, with the rival + verbatim evidence + the residual delta as
claimed and why it fails.
EDIT NOTHING; spawn NOTHING; assign NO numeric score. WRITE ONLY this JSON to <OUT> (no prose around it):
  { "verdict": "complete"|"incomplete"|"scooped", "padding": [ { "key": "...", "why": "..." } ],
    "miscited": [ { "key": "...", "claim": "...", "why": "..." } ],
    "uncovered_comparators": [ "<diff-table row or borrowed theorem with no/incorrect canonical cite>" ],
    "thin_threads": [ "<positioning thread missing origin or frontier>" ],
    "scooped_by": { "rival": "<title + arXiv/DOI>", "evidence": "<verbatim quote>",
                    "claimed_delta": "<the delta the table claims, or 'none stated'>",
                    "why_delta_fails": "<one line>" },   // REQUIRED iff verdict=scooped, else omit
    "summary": "<one line>" }
