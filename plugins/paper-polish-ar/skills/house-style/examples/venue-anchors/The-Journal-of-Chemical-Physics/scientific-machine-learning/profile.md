<!-- Machine-read venue contract for The Journal of Chemical Physics (AIP) / SciML. Resolved at runtime
     from the request (the NL prompt names the venue; there is no config fallback and never a silent
     `default`) and threaded into every reviser / reviewer / AC goal. overall.md stays the human
     narrative + paper roster; this file is the fielded contract that /polish and /review consume. Seven
     blocks; keep them all.
     NOTE: this is *The Journal of Chemical Physics* (AIP Publishing, chemical physics), NOT the sibling
     venue *Journal of Computational Physics* (Elsevier). They share the "JCP" abbreviation only. -->
# Venue profile — The Journal of Chemical Physics / scientific-machine-learning

## identity
- venue: The Journal of Chemical Physics (AIP Publishing; abbrev. J. Chem. Phys.)
- field: scientific machine learning
- type: specialist chemical-physics journal — broad within chemical physics, not general-science
- audience: chemical physicists; assume quantum & statistical mechanics, electronic-structure and molecular-simulation fluency
- not to be confused with: Journal of Computational Physics (Elsevier) — a different venue with the same "JCP" initials

## register
Confident, concrete, quantitative, mechanism-forward, and technical-first. Methods, equations, error
metrics, and benchmarks carry the prose; this is the equation- and algorithm-dense pole (Nature-family
registers are deliberately far less dense). Define every object precisely, name the system / method /
benchmark, report numbers and comparisons, and state the **physical** mechanism — why the method works,
and what chemical-physics it captures — soberly. JCP rewards one thing the pure-numerics register does
not: a crisp statement of the underlying *chemical-physics question* and the physical insight, with
approximations and assumptions made explicit. No broad-audience framing, no hype; a JCP reader wants the
contribution, the physics, and the evidence, not the sell.

## vocabulary
### venue-acceptable in moderation
These read as normal technical usage here and appear in the venue's own published prose. Do NOT flag on
every occurrence; flag only the vague / non-technical / over-used case.
- robust / robustness — technical sense ("robust to noise / to out-of-distribution structures") OK; flag only when vague ("a robust framework" with no referent).
- comprehensive — "a comprehensive benchmark / assessment" OK; flag as empty filler.
- crucial / crucially — OK once; flag on overuse (more than ~once per section).
- underscore — "the results underscore X" OK; flag on overuse or as a hype connector.
- significant / significantly — statistical or clearly-quantified sense OK; flag as a vague intensifier.
- consistently — OK when describing a measured trend.

### venue-stricter
(none beyond the global banned-vocabulary list)

## conventions
- spelling: American (AIP house style: "good scientific American English")
- abstract: unstructured single paragraph, funnel shape; "Here we show" / "we demonstrate" acceptable; ~250 words; NO displayed equations, references, footnotes, graphics, or tables
- title: descriptive but specific (name the method/model and the chemical-physics system or question); declarative finding-titles uncommon
- references: numbered (AIP style — `Ref. 19`, superscript `19`, or `Hernandez et al.`19); dense citation acceptable
- sections: Introduction → Theory/Methods (inline, early) → Results/Applications → Discussion/Conclusion; Methods is NOT moved to the end (unlike Nature)
- math/display: display equations expected and frequent; punctuate them, align to show structure, number on the right-hand side; define every symbol before first use
- figures: spectra, potential-energy surfaces, convergence / error plots, and benchmark tables expected; multi-panel OK; embed in text with alt text; no decorative figures
- required statements: a Data Availability statement is mandatory

## acceptance-bar
The detailed form for the /review panel lives in review/. Summary, also used as the keynote effort prior:
- reviewers reward: rigorous quantitative validation; error / uncertainty analysis and convergence (basis, sampling, finite-size) wherever accuracy is claimed; explicit approximations and assumptions; fair and complete baselines; ablations that isolate the claimed mechanism; a clearly stated physical mechanism / chemical-physics insight; reproducibility (system setups, hyperparameters, seeds, data, error definitions); and that the work answers a real chemical-physics question.
- reject triggers: applying a method to a chemistry / materials *application* with no chemical-physics insight; insufficient or cherry-picked evidence; unstated approximations or missing uncertainty analysis; unfair or missing baselines; overselling generality beyond what the experiments show.
- novelty / significance bar: a clear methodological or physical advance over existing chemical-physics / SciML work, demonstrated quantitatively. Field-internal (chemical-physics) significance is enough; broad general-science / interdisciplinary reach is NOT required (this is a specialist venue).
- panel kit: review/rubric.md + review/reviewer-profiles.md + review/scoring.md.

## limits
- abstract ~250 words (single paragraph, no equations/refs).
- Communication ≤3500 words (excluding figures, tables, references); Note ~2 journal pages.
- Article: no hard main-text length limit, but concision is rewarded.

## anchors
- register narrative: overall.md
- before→after few-shots: none shipped (see ../../_TEMPLATE/)
  MACE-MP-0, arXiv:2401.00096, physics.chem-ph — the advisor's representative paper; the venue
  register/voice anchor)
