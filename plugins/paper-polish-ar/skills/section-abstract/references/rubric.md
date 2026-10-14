# Abstract and Title — rubric

Acceptance criteria for the title and abstract. Each item gets a verdict (pass / partial / fail)
plus evidence quoted from the text. The overall shape is a **funnel**: broad field → specific
problem → core finding → far-reaching conclusion.

## How this section is run (special case)
The original prompt asks for *several* title/abstract options to choose from. Under autonomous
operation this becomes **revise-and-auto-select**: the reviser makes the **minimal necessary
revision** of the *existing* title + abstract (it does NOT write a fresh abstract from scratch —
that is what drove whole-abstract churn), producing 2-3 candidate revisions that keep every sentence
that already reads well. The evaluators judge each candidate HEAD-TO-HEAD against the original
(categorical: clearly_better / marginally_better / not_better — no numeric scores), and **two gates
disqualify a candidate before the comparison is weighed**: fidelity (meaning preserved) and the
check-ai-tells zero-tolerance gate (any surviving em-dash / banned word / interchangeable-template
phrasing). No head-to-head win rescues a dirty candidate. **Do-no-harm floor:** the original is
replaced only when a *clean* candidate is judged *clearly* better ("marginally better" = churn);
otherwise keep the original. Record the runners-up and the disqualified candidates in the round commit. Abstract is
polished **last**, after the body is settled, so it summarizes the finalized paper.

## Title
1. **Grabbing.** The title is attention-catching and compelling, not a flat descriptive label.
2. **Accurate.** It promises exactly what the paper delivers — no overreach. *(Scaffold addition —
   not in the original prompt, which asked only for a grabby title; kept because it aligns with the
   freeze-the-claims rule and top-journal norms.)*

## Abstract — sentence-function skeleton (latent, never literal)
Treat these as the functions the abstract must perform, not as a fill-in-the-blank template. Two
abstracts that both satisfy this should not sound interchangeable. **Few-shot** (weak draft → the
polished JCP abstract, for tone + funnel when this section is hard): (no example ships in this release; add your own under `house-style/examples/venue-anchors/`).

**Abstract shape follows the selected venue profile's `## conventions`** (named in your goal's TARGET
VENUE preamble): the profile specifies the shape (for example an unstructured single-paragraph funnel,
a broad-audience summary paragraph, or a labeled structured abstract) and whether a "Here we show" turn
fits. The functions below are venue-independent; only their packaging follows the profile.

1. **Background, broad reach.** One or two sentences set the macro, high-interest field and why it
   matters, readable by a scientist outside the subfield.
2. **Specific gap / challenge.** A turn (e.g. "However") names the key unsolved problem — the
   reason this work is needed.
3. **Core finding.** Introduced with a direct marker ("Here we show" / "We report"), states the
   single most important result, and includes **1-2 key quantitative data points when the paper has
   them**. *(The original prompt "strongly recommends" the quantitative data; treat it as
   **preferred, not required**. A precise qualitative finding does **not** fail this item, and an
   abstract is **never** rewarded for dumping in more numbers. Never fabricate a number — and never
   promote a qualitative result to a quantitative one — to satisfy this; the freeze boundary forbids
   inventing data. Prefer the number the paper already reports; if the draft genuinely has none, that
   is not a failure.)*
4. **Evidence + mechanism.** One or two sentences give the strongest supporting evidence (the key
   experiment or method) and the "why" behind the finding.
5. **Significance + universality.** A closing turn ("Our findings" / "Together") answers what
   changes, and naturally hints that the approach generalizes beyond this one example.

## Anti-patterns (flag)
- Core finding stated vaguely when the paper reports a concrete result that could ground it (the fix
  is precision, not a number for its own sake — a genuinely qualitative finding stated sharply is fine).
- Abstract reads as a list of everything done rather than a funnel to one finding.
- Sounds interchangeable with any other abstract (template seams visible — see ai-tells).
- Significance over-claimed beyond what the paper supports.
- Title is descriptive-only / not compelling.

---

[FILL IN: extra abstract/title criteria you and your advisor apply.]
