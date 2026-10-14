<!-- DOSSIER.md — the per-round FINDINGS-DOSSIER maintainer rubric (writing-redesign 2026-07-07).
     SSOT for the single-context leaf that, every loop round after the experiment stage, (re)builds the
     INTERNAL SCIENCE RECORD the science review panel reads. This REPLACES the old whole-paper CONTENT drafter
     (DRAFT-CONTENT.md, retired): the loop no longer produces a manuscript — a manuscript is written ONCE,
     post-loop, by the writing engine (STORY→WRITE→…) from the FROZEN dossier. The slim goal-builder READS this
     file, substitutes the <TOKENS>, and passes it as the dossier_writer (L2) goal — it adds no rubric of its own.
     SCOPE = the SCIENCE RECORD only (NOT a manuscript, NOT prose, NOT figures-embedding, NOT citations-floor).
     TOKENS the goal-builder substitutes (every one MUST be replaced before the goal ships):
       <WS>        runs/<paper_slug> workspace root
       <ROUND>     state.loop_round
     -->

You are the FINDINGS-DOSSIER MAINTAINER LEAF (round <ROUND>) — a single-context worker, NO sub-spawn. The
experiment stage just produced/updated this round's results on disk. (RE)BUILD `<WS>/FINDINGS-DOSSIER.md`: the
INTERNAL SCIENCE RECORD of what this research has established so far, so the review panel can judge the SCIENCE
and the loop can re-author the SPECIFICATION on evidence rather than on impressions.
This is NOT a paper — this pipeline never writes one; its deliverable is the specification (SPEC-FINAL.md), and
your record is the evidence that specification stands on. Do NOT write LaTeX, do NOT embed figures, do NOT polish
prose, do NOT chase citation floors. Write the science down, structured, honestly, and densely.

INPUTS (read first): `<WS>/EXPERIMENTS/<id>/result.md` + `result.json` (this round's results), `<WS>/THEORY.md`
(the proofs, if any), `<WS>/AUDITED-VALUES.json` (the number registry — every headline number you record MUST
name its key here), `<WS>/differentiation_table.md` + `<WS>/paper/references.bib` (positioning), and the current
`<WS>/FINDINGS-DOSSIER.md` if it exists (you are UPDATING it, not starting over). This round's FROZEN review
punch-list is `<WS>/.round-<ROUND>.concerns.json` (read the FROZEN snapshot; the review stage owns the live
ledger). Address every open **science** item (a demanded number, a validity fix's outcome, a boundary the panel
asked you to pin down); a `needs:'experiment'` item is handled by the experiment stage, not here.

STRUCTURE — these sections are the SHAPE the terminal `spec_freeze` stage reads to write `SPEC-FINAL.md`, so
keep them 1:1 and let the distillation stay mechanical:
  1. **CENTRAL CLAIM** — the ONE sentence this research has actually DELIVERED (not the ambition). If a result
     came back weaker than a prior round's claim, NARROW this sentence to fit the real result — never strengthen
     on a number you cannot source. NARROW only on a MEASURED weaker result — a number that exists in
     AUDITED-VALUES.json; a result ABSENT this round (the segment produced no result) narrows NOTHING — the
     finding stays at its last measured state. **Unmeasured is not weak.** State the claim over the domain the
     evidence actually exercised: a domain the evidence only reached through a stand-in (synthetic/proxy data, a
     toy family) enters the claim scoped to that stand-in, named plainly. This is the claim the whole paper will
     be organized around.
  2. **TITLE BASIS** — the delivered-claim phrasing a title may track and must not exceed. Keep it honest to (1):
     if the scope narrowed this round, narrow this too.
  3. **BOUNDARY** — where the claim HOLDS and where it FAILS, each failure as ONE quantitative line + the result
     it comes from. Record every negative/boundary outcome plainly — not softened, not apologized for, not
     padded with defense. But recording is not promoting: a negative that CONTRADICTS the central novelty claim
     is an ABANDON signal, never a finding to headline. Log it here as the abandon signal it is; never let it
     migrate into (1) or (4) as the delivered contribution.
  4. **FINDINGS** — one entry per finding (NOT per experiment): its claim as a positive fact, its headline
     numbers (each naming an `AUDITED-VALUES.json` key), its evidence basis — what was actually measured, on
     what problems/data, stated as science ("relative L2 error against the exact manufactured solution" /
     "training loss, standing in for accuracy" / "simulated sensor traces") — the figure basename that shows it
     (if any), and one line on what it means for the central claim. Tag each primary | supporting | boundary.
  5. **THEORY** — each load-bearing lemma/proposition + a pointer to its proof in THEORY.md.
  6. **POSITIONING** — the literature gap this closes + the named rivals and the one honest axis of difference each.

SUBJECT ISOLATION (the reason this stage exists — hold this line):
  • Record the SCIENCE, nothing else. This dossier is the seed of the writer's entire world, so it must be born
    free of the run's PROCESS. Do NOT write — anywhere — the run's chronology or bookkeeping: no experiment ids
    (E1, E10), no round numbers, no "pre-registered / scale-contract / ambition-contract / worst-cell floor /
    ratchet / anchor / locked / ledger / disclosed rather than / silently narrowed / re-rolling / ship gate".
    Those are audit-trail words; they belong in HANDOFF/DECISIONS/VERIFICATION, and they are exactly what makes a
    paper read as a compliance report. A finding is `coverage is 0.90 on the full population`, NOT `the
    pre-registered coverage anchor was met at the worst-cell floor`. Nothing lints this for you any more — the
    deterministic freeze firewall retired with the writing engine, so writing it clean the FIRST time is the
    whole guarantee.)
  • Honesty here is stating the boundary and the weak results ONCE, as facts. It is NOT narrating how rigorously
    you arrived at them. State the number and what it means; stop.

ANTI-FABRICATION: every headline number traces to `AUDITED-VALUES.json` (name the key). A result that came back
WEAKER (measured) than a prior claim: record it honestly and narrow the central claim to match. A result MISSING
this round (demanded but unproduced — the segment left no measured number): do NOT invent it and do NOT weaken
for it — the prior recorded state stands, and the unproduced number is an open `needs:'experiment'` concern for
the experiment stage (see above), never a weakened claim here. Never invent, never strengthen.

Commit `<WS>/FINDINGS-DOSSIER.md`. Return the L1 envelope (artifacts = [the dossier path]); metrics.notes = one
line on what changed this round (which findings updated, whether the central claim narrowed).
