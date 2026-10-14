<!-- Machine-read venue contract for the DEFAULT fallback register. Resolved when config.target_venue is
     null or unset. Represents a conservative generic top-journal register applicable to any scientific
     paper. overall.md is the human narrative; this file is the fielded contract /polish and /review
     consume. Seven blocks; keep them all. -->
# Venue profile — default / generic top-journal

## identity
- venue: generic top-journal (fallback; no specific venue set)
- field: the paper's own field (resolved from manuscript context)
- type: generic top-journal register — applicable to any peer-reviewed science venue
- audience: any scientist in the paper's own field; assume field-standard fluency, not cross-field breadth

## register
Confident, concrete, quantitative, restrained, and honest about limits. Evidence and mechanism carry
the prose: report numbers, name the comparison, state what the method does and why it works. Do not
oversell scope or generality beyond what the experiments show. No hype, no broad-audience framing
designed to impress a non-specialist, no defensive hedging that obscures a genuine result. A reader
in the paper's own field wants the contribution and the evidence; give them that without the sell.

## vocabulary
### venue-acceptable in moderation
(none — this profile inherits the STRICT global banned-vocabulary reading with no venue exceptions.
Consult references/banned-vocabulary.md for the full list. All flagged words are flagged here.)

### venue-stricter
(none beyond the global banned-vocabulary list)

## conventions
- spelling: American
- abstract: unstructured single paragraph, funnel shape; state the gap, the contribution, the result
- title: descriptive; name the method and the problem; declarative finding-titles acceptable
- references: numbered bracket [n]; author-year acceptable if the venue uses it
- sections: Introduction → Methods (inline, before Results) → Results → Discussion; SI for supplementary material
- math/display: define every symbol before first use; display equations for anything that must be reproduced
- figures: show the key comparison; multi-panel OK; no decorative figures

## acceptance-bar
The detailed form for the /review panel lives in review/. Summary, also used as the keynote effort prior:
- reviewers reward: sound evidence for every claim; clear, demonstrated contribution relative to prior work; honest statement of limits; fair and complete baselines; reproducible methods.
- reject triggers: unsupported or overclaimed results; missing or unfair baselines; conclusions that outrun the evidence; generality asserted but never tested.
- novelty / significance bar: a clear, demonstrated contribution that advances the field's understanding or practice — incremental novelty presented as a major advance is penalized; genuine advances need not be broad to matter.
- panel kit: review/rubric.md + review/reviewer-profiles.md + review/scoring.md

## limits
- (none enforced by this profile; defer to the actual submission venue's stated limits)

## anchors
- register narrative + paper roster: overall.md
- before→after few-shots: abstract.md, introduction.md, results.md, methods.md, discussion.md
- example paper(s): (none yet — add entries as papers are reviewed under the default profile)
