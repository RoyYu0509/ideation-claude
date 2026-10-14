# Ideation JSON schema (v2 — verified-kill redesign, 2026-07-11)

Build the ideation output dict to this shape, then run the validating writer
(do NOT hand-write the final JSON to `output_path`). v2 additions over v1:
per-idea `falsifier_thresholds` + `routes_through`, premise rows carry
`probe_class` (+ pre-registered `criterion` when required), asset entries carry
`needed_paths`. `priority_pick` is RETIRED — the independent screener ranks.
Rounds 2+ write the same schema to `<arxiv_id>-r<R>.json`.

```json
{
  "arxiv_id": "<from input>",
  "week": "<from input>",
  "round": 1,
  "title": "<the paper's title, copied VERBATIM from input>",
  "paper_summary": "<from step 3>",
  "why_relevant": "<from step 3>",
  "depth_signal": "websearch_used | landscape_scanned | pdf_fetched",
  "landscape_context": {
    "direction_saturation": "low | medium | high",
    "known_competitors": ["Paper Title A (arXiv:XXXX)"]
  },
  "has_journal_level_idea": true,
  "ideas": [
    {
      "idea_type": "new_direction | direct_extension | challenge_and_improve",
      "contribution_type": "new_theorem | new_method | new_application | new_empirical_finding",
      "significance_status": "paper_worthy | borderline | incremental",
      "working_title": "...",
      "claim": "<FROZEN once written — the verified-kill loop string-compares it downstream>",
      "method_sketch": "...",
      "significance_note": "...",
      "sharp_falsifier": "...",
      "falsifier_thresholds": [
        { "value": 2.5, "units": "log-log slope",
          "src": "src: O(h^3) theoretical rate, arXiv:XXXX Thm 2" }
      ],
      "routes_through": ["P1"],
      "load_bearing_premises": [
        {
          "premise": "one falsifiable sentence about the TARGET/benchmark/data (never the method's own construction)",
          "status": "verified | unverified",
          "source": "REQUIRED when verified — p.X, §Y: \"verbatim quote\"",
          "probe": "REQUIRED when unverified — the concrete cheap check",
          "probe_class": "required | deferrable",
          "criterion": { "metric": "<with units>", "direction": "<= | >= | < | >",
                         "threshold": 1.0, "threshold_src": "src: <anchor>" },
          "consequence_if_false": "one line: what dies"
        }
      ],
      "asset_manifest": [
        {
          "url": "https://github.com/...",
          "kind": "repo | dataset | checkpoint | benchmark-code",
          "needed_for": "one line",
          "needed_paths": ["gen/*.py", "data/*.h5"],
          "status": "verified_live | stub_or_empty | missing | unverified",
          "evidence": "what you saw, or 'declared — screen verifies'"
        }
      ],
      "why_novel_despite_landscape": "Required when landscape_context.known_competitors is non-empty; else null."
    }
  ],
  "notes": "optional: warnings, e.g. 'abstract was mechanism-thin, used Tier 3'"
}
```

Premise ids are positional: `P1` = `load_bearing_premises[0]`, `P2` = `[1]`, …
(`routes_through` uses these ids). A premise the falsifier routes through, or
one about a named benchmark/dataset's construction, MUST be
`probe_class: "required"` with a complete `criterion` — the independent
verifier implements and executes exactly that probe.
