# Commit protocol for polishing rounds

## Message format

```
polish: round <N> — <section>

<one line per hunk: rule-tag + rationale>
addresses: <which evaluator flags from the previous round this round answers>
```

## Rules

- **One commit per round per section.** The per-round git history is the deliverable the author
  reads; do not amend or squash.
- **Meaning-drift restores get their own follow-up commit** (so the history shows the slip and
  the fix, separately).
- Stage the section file only: `git add -- <section-file>`. Never `git add -A` — that risks
  pulling in unrelated working-tree changes.
- The polish branch is created by the orchestrator; the base commit (original text) is its first
  commit. Never commit to `main` directly.
