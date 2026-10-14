<!-- Machine-read venue contract for JCP / SciML. Resolved from config.target_venue and threaded into
     every reviser / reviewer / AC goal. overall.md stays the human narrative + paper roster; this file
     is the fielded contract that /polish and /review consume. Seven blocks; keep them all. -->
# Venue profile — Journal of Computational Physics / scientific-machine-learning

## identity
- venue: Journal of Computational Physics
- field: scientific machine learning
- type: specialist methods journal (not broad-audience)
- audience: computational scientists; assume PDE / numerics / ML fluency

## register
Confident, concrete, quantitative, restrained, and technical-first. Methods, equations, error metrics,
and benchmarks carry the prose. More equation- and algorithm-dense than a Nature-family register:
define objects precisely, name the PDE/benchmark, report numbers and comparisons, and state the
mechanism (why the method works) soberly. No broad-audience framing, no hype; a JCP reader wants the
contribution and the evidence, not the sell.

## vocabulary
### venue-acceptable in moderation
These read as normal technical usage here and appear in the venue's own published prose. Do NOT flag on
every occurrence; flag only the vague / non-technical / over-used case.
- robust / robustness — technical sense ("robust to noise", "the method's robustness") OK; flag only when vague ("a robust framework" with no referent).
- comprehensive — "a comprehensive evaluation/study" OK; flag as empty filler.
- crucial / crucially — OK once; flag on overuse (more than ~once per section).
- underscore — "the results underscore X" OK; flag on overuse or as a hype connector.
- significant / significantly — statistical or clearly-quantified sense OK; flag as a vague intensifier.
- consistently — OK when describing a measured trend.

### venue-stricter
(none beyond the global banned-vocabulary list)

## conventions
- spelling: American
- abstract: unstructured single paragraph, funnel shape; "Here we show" / "we demonstrate" acceptable; ~150-250 words
- title: descriptive but specific (name the method and the problem); declarative finding-titles uncommon
- references: numbered bracket [12]; dense citation acceptable
- sections: Introduction → Methods (inline, early) → Results → Discussion; Methods is NOT moved to the end
- math/display: display equations expected and frequent; define every symbol before first use
- figures: convergence plots and error tables expected; multi-panel OK; no decorative figures

## acceptance-bar
The detailed form for the /review panel lives in review/. Summary, also used as the keynote effort prior:
- reviewers reward: rigorous numerical validation on canonical benchmarks; error / convergence analysis; fair and complete baselines; ablations; a clearly stated mechanism for why the method works; reproducibility (hyperparameters, seeds, problem setups).
- reject triggers: insufficient or cherry-picked numerical evidence; unfair or missing baselines; claims not backed by error metrics; overselling generality beyond what the experiments show.
- novelty / significance bar: a clear methodological advance over existing SciML / numerics methods, demonstrated quantitatively. Broad interdisciplinary appeal is NOT required (this is a specialist venue).
- panel kit: review/rubric.md + review/reviewer-profiles.md + review/scoring.md.

## limits
- abstract ~150-250 words; no hard main-text page limit, but concision is rewarded.

## anchors
- register narrative: overall.md
- before→after few-shots: none shipped (see ../../_TEMPLATE/)
