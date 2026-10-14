---
name: config-value-injection
description: Use whenever you edit or "optimize" any plugin markdown — a slash-command file (commands/*.md, .claude/commands/*.md) or a SKILL.md. Enforces the config-SSOT rule — every literal that mirrors a config/config.yaml key must be a dynamic cfgval.sh injection span, never a hardcoded number/string — and the substitution must be MINIMAL (replace the value in place; never rewrite the surrounding sentence).
disable-model-invocation: false
allowed-tools: Read, Edit, Grep, Bash(*cfgval.sh*)
---

config.yaml is the single source of truth. Markdown (command files + SKILL.md)
is compiled by the Claude Code harness at load time: a `bin/cfgval.sh <key>`
**injection span** is run and replaced by its stdout. So a config value belongs
in the markdown as a live injection, never as a frozen literal that drifts.

In this doc, **`INJECT(key)`** stands for one injection span. Its exact literal
syntax is a bang, a backtick, `"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" key`, then a
closing backtick. Do NOT write that token here as plain text — it would execute
when THIS skill loads. For the real on-disk form, open any of
`skills/arxiv-rerank/SKILL.md`, `skills/arxiv-generate/SKILL.md`,
`skills/arxiv-plan/SKILL.md` — they all use it with live keys.

## The one rule

Any literal in the prose that corresponds to a key in `config/config.yaml` MUST
be written as `INJECT(<dotted.key>)`. `cfgval.sh` takes a dotted path
(`scout.prefetch_top_k`, `rerank.multi_thread_threshold`) and prints the resolved
value; the harness compiles it to the live value when the command/skill loads.

## Minimal substitution — do NOT do more than this

Replace the literal **in place** and stop. Keep the surrounding sentence
byte-for-byte identical otherwise.

- ✅ `Do NOT ideate papers whose extensibility_verdict is below the INJECT(scout.extensibility_gate) tier from Phase 3.`
- ❌ `Do NOT ideate papers with extensibility_verdict below ``scout.extensibility_gate`` (currently INJECT(scout.extensibility_gate)) from Phase 3.` — reworded, restructured, added "(currently …)".

Forbidden when doing an injection edit: adding "(currently X)", "exactly as
`workflows/arxiv-scout.js` does", renaming the metric, re-wrapping in inline-code
spans, or any prose the original sentence did not have. The injection reads as the
value at load time — the sentence already flows.

Backtick nesting: an injection span already uses backticks. Do NOT wrap the whole
`INJECT(...)` span in an inline-code span — bare is correct (see the arxiv-rerank /
ideate / refine skills). And never write the literal injection token inside a file
as a non-executing *example* — escape it via the `INJECT()` convention above, or
the harness will run it on load (this skill itself hit that bug once).

## Procedure when editing/optimizing a markdown file

1. Grep the file for literals that smell like config: bare integers, thresholds,
   enum values, counts, `--top-k N`, `score < N`, "top N", round limits.
2. For each, check `config/config.yaml` for a matching key, and confirm how the
   canonical `workflows/arxiv-scout.js` reads it (`req(KNOBS, '<key>')`). The
   dotted path is the same key path (e.g. `scout.<key>`).
3. Replace the literal in place with `INJECT(<key>)`. Nothing else.
4. Verify the key resolves before finishing: `bash bin/cfgval.sh <dotted.key>`
   must print a value (not empty / not an error).

## Not every number is a config value

Template/illustrative placeholders (e.g. a `{rerank_return_n}` token shown inside
a fenced format example) and references that already name the key instead of a
literal (e.g. "at most `candidates_per_round` candidates") are already correct —
leave them. Only frozen literals that duplicate a config value get injected.
