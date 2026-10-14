<!-- polish-recommend-venue.md — the best-fit target-venue recommender rubric (/polish Phase-0).
     SSOT for the ONE read-only reviewer that picks the best-fit venue from a FIXED prepared list when the
     /polish request named none. It RETURNS only (a subagent can never ask the author); the orchestrator
     runs the AskUserQuestion picker over the result. Extracted out of spec/polish.js (recommendVenue's
     goal-builder); the slim goal READS this file, substitutes the <TOKENS> below, appends the reviewer
     thinking block (NO venue preamble — the venue is undecided), and passes it as the reviewer goal.
     It returns RECOMMEND_SCHEMA (enforced at the call site).
     TOKENS the goal-builder substitutes (every one MUST be replaced before the goal ships):
       <CONTEXT>        the title/abstract/opening source files (comma-joined)
       <PREPARED_LIST>  the exact prepared-venue rels, each quoted, comma-joined
-->

Recommend the best-fit target venue for this paper from a FIXED list. Read ONLY the title,
abstract, and opening of: <CONTEXT>. Choose the single best match from this exact list of
prepared venues (return the string VERBATIM): <PREPARED_LIST>. If the
paper's topic/methods do not clearly fit any, return recommended_venue: null. Do NOT invent a venue
not in the list. Return RECOMMEND_SCHEMA.
