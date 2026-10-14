# Third-party notices

## Vendored skills

The skills in `skills/nature-academic-search` and `skills/nature-reader` are vendored verbatim from https://github.com/Yuan1z0825/nature-skills (MIT License, Copyright (c) 2026 Yuan Yizhe). nature-reader keeps its native router format; nature-academic-search was DOWNGRADED 2026-07-06 (dossier-12 H1) to a WebSearch/WebFetch multi-source guide — its never-registered MCP machinery (`mcp-server/`, `install.sh`, `manifest.yaml`, `static/`, `scripts/`, `config/`) is archived local-only under `stale/nature-academic-search-mcp/`. They are venue-neutral capabilities (multi-source literature search; in-depth PDF reading) retrieved by `/review`'s investigator + experimenter.

Note: the upstream Nature-family skills `nature-figure`, `nature-citation`, `nature-paper2ppt`, and `nature-response` were **removed** — this plugin is scoped to computational-science journals (JCP/CMAME/SISC), not the Nature/CNS family. The `nature-figure` plotting know-how that is venue-neutral was internalized into `skills/research-figure-plotting`; its venue-neutral DESIGN layer (the conclusion→evidence→archetype figure contract) now lives in `skills/figure-design` (original work, not vendored); the Nature-aesthetic figure workflow is deliberately not shipped (see `/polish-figures`).

Writing and review knowledge from the `nature-reviewer`, `nature-writing`, and `nature-polishing` skills in the upstream repository was adapted (not copied verbatim) into this repository's `skills/house-style/`, `skills/section-*/`, and `skills/check-*/` skills, also under the MIT License (Copyright (c) 2026 Yuan Yizhe).

A full upstream snapshot is kept locally at `vendor/nature-skills/` for provenance during development. It is **gitignored** (about 64 MB, fully reproducible), so it is not committed; re-fetch it with `git clone --depth 1 https://github.com/Yuan1z0825/nature-skills vendor/nature-skills`.

## Vendored from the author's local skills

`skills/research-figure-plotting` is vendored from the author's cross-project skill library (`~/.claude/skills/research-figure-plotting`) so the `/polish-figures` workflow is self-contained and reproducible without depending on that skill being installed on the running machine. It is the visual capability `/polish-figures` retrieves (the multi-panel layout / legend / colorbar / typography playbook + render-and-look visual QA). Keep the two copies in sync if the upstream one changes.

## Local modifications to vendored skills

To resolve skill-routing conflicts inside this plugin, a vendored skill carries a small local edit to its **frontmatter only** (its body logic, `static/`, `references/`, `scripts/`, and `manifest.yaml` are untouched):

- `skills/research-figure-plotting` — `user-invocable: false` was added so it is retrieved only inside the `/polish-figures` workflow rather than invoked directly out of context.

These are the only deviations from the upstream copies and are trivial to re-apply after an upstream re-sync.
