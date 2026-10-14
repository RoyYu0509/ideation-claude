# Evidence sidecar JSON schema

Build this dict, then write it via the validating writer
(`ideate_save.py --kind evidence`, see Step 5b) — do NOT hand-write the final
JSON to `evidence_path`:

```json
{
  "arxiv_id": "<from input>",
  "week": "<from input>",
  "pdf_quotes": [
    {
      "page": 4,
      "section": "Method 3.2",
      "quote": "verbatim quote of the key sentence(s) you used to understand the mechanism",
      "why_useful": "1 sentence — why this passage matters for an extension or a cross-paper fusion"
    }
  ],
  "websearch_findings": [
    {
      "url": "https://...",
      "takeaway": "1-2 lines summarizing what this source told you about the method or its context"
    },
    {
      "url": "https://arxiv.org/abs/...",
      "takeaway": "REQUIRED here too — S2 landscape hits are ordinary entries plus the type key",
      "type": "landscape"
    }
  ],
  "rejected_candidates": [
    {
      "working_title": "<candidate idea you considered but cut>",
      "why_rejected": "1 sentence — which of the four sub-fields it failed (no sharp falsifier / hand-waved method / etc.) OR why it was a worse fit than a kept idea"
    }
  ],
  "cross_thread_hints": [
    {
      "thread": "<another thread label from profile.json — NOT thread_context>",
      "connection": "1 sentence — the specific way this paper's contribution also touches that thread; the kind of cross-paper hint the downstream stages or the seed→HANDOFF pipeline might use"
    }
  ]
}
```
