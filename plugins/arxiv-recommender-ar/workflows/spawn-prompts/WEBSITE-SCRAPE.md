<!-- WEBSITE-SCRAPE.md — the Phase 0a website paper-list extraction rubric for arxiv-scout (profile rebuild).
     SSOT for the website-scrape leaf that reads a researcher's personal site and returns its paper list. There is
     NO skill home for this step, so this file is the only home; the slim Phase 0a goal-builder READS this file,
     substitutes the <TOKEN> below, and passes it as the leaf goal — it adds no rubric of its own. The return JSON
     ({papers[], scrape_failed} = the WEBSITE_PAPERS_SCHEMA) is enforced by the orchestrator via the spawn schema.
     TOKENS the goal-builder substitutes (every one MUST be replaced before the goal ships):
       <WEBSITE_URL>  the researcher's personal_website (config researcher.personal_website)
-->

You are the website-scrape step (Phase 0a) of the arxiv-profile workflow.

Task: Extract ALL papers listed on the researcher's personal website.
Website URL: <WEBSITE_URL>

Instructions:
  1. WebFetch the website URL.
  2. Extract ALL paper entries visible on the page: title (required),
     year (if shown), venue/status (if shown), co-authors (if shown).
     Include published AND under-review papers. Skip books and theses.
  3. Nav-page fallback: if the fetched page is a navigation shell / landing page
     with no real paper entries (e.g. a Google-Sites nav that only links to
     sub-pages), DO NOT hand-author or compile a paper list from nav links or
     from memory — return {"papers": [], "scrape_failed": true} so the
     deterministic JS fallback (in scripts/build_profile_papers.py, wired at
     arxiv-scout.js ~L310) runs: it does a direct Semantic Scholar author fetch
     when researcher.s2_author_id is set, and otherwise keeps any existing
     profile rather than fabricating one.
     Do not attempt the S2 fetch yourself: this leaf has no s2_author_id.
  4. Return a JSON object with field "papers" (array of paper objects).
     If the page cannot be scraped or has no papers, return
     {"papers": [], "scrape_failed": true}.

Important: extract titles exactly as shown — do not paraphrase or truncate.
