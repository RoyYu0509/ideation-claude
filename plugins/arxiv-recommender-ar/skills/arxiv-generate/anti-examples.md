## Significance categories

This measures AMBITION, not rigor. Every idea gets one of three categories (the same vocabulary the downstream refine step uses):

| Category | Meaning |
|---|---|
| `paper_worthy` | A **new mechanism / principle / problem framing** — if true, the field's understanding or practice changes (not one benchmark cell), not reducible to "method X applied to setting Y"; OR a substantive adaptation, fusion, or transfer of a mechanism so a **new capability or guarantee emerges that did not exist before** — including carrying a mechanism from field A into field B where an effect neither field had appears (奇效). A top-venue reviewer could call it a new contribution to the field. |
| `borderline` | Modest extension or verification: a port to an adjacent setting where no new capability emerges and the outcome is foreseeable, OR an experiment whose only deliverable is to confirm / refute / measure / attribute an already-reported pattern. Nothing new is left behind. |
| `incremental` | Narrow re-application or pure optimization: a port or a metric-improvement with no new mechanism, guarantee, or capability. Foreseeable outcome. **Not paper-worthy.** |

**What is NOT a research idea** (`borderline` or `incremental` — never a seed): work whose only deliverable is to verify / confirm / refute / measure / **attribute** / optimize something already reported — including a counterfactual-control experiment that judges a pattern's *cause* (e.g. "is Regime II an optimizer artifact?"), even when framed as "首次因果分解 / 归因". `new_empirical_finding` means a phenomenon *newly discovered*, never the attribution of a reported one. A seed must leave a NEW artifact behind. Concrete anti-examples and their generative repairs follow below.

---

# Anti-examples — what is NOT a research idea

The single test is **generativity**: after the idea succeeds, is there a NEW artifact in the world (a new mechanism / method / capability / theorem / direction / a genuinely newly-discovered phenomenon)? If the only deliverable is to **verify / confirm / refute / measure / attribute / optimize** something already reported, it is `borderline` or `incremental` and is **not a seed** — no matter how sharp its falsifier or how specific its method_sketch. Each anti-example pairs the non-idea with a generative idea the SAME paper could seed instead.

## 1. Attribution / counterfactual-control (the most disguised — verification wearing a "discovery" costume)
❌ *"Re-run the paper's diagnostic grid with a gradient-free least-squares solver to determine whether Regime II is an optimizer artifact vs intrinsic."* — The deliverable is an **attribution** of an already-reported pattern's cause; you only learn yes/no about someone else's observation. Calling it "first causal decomposition / 首次因果归因" does NOT make it generative, and it is NOT a `new_empirical_finding` (that means a *newly discovered* phenomenon, not the attribution of a reported one). → `borderline`.
✅ Generative repair: *"A new regime-aware scheduler that, from an early-training curvature probe, predicts a config's failure regime before full training and routes to the regime-optimal method."* — leaves a new method/capability behind.

## 2. Measuring / confirming a reported pattern
❌ *"Measure the gradient-variance / barren-plateau scaling of this paper's ansatz."* — The paper already states it observes no barren plateau; the only deliverable is to confirm/quantify that. → `borderline`.
✅ Generative repair: *"A convexity-certified polynomial cost (SOS + admissibility barrier) that provably preserves the energy functional's unique-minimizer guarantee under quantum-implementable truncation."* — a new cost-design mechanism.

## 3. Robustness verification ("does the pattern still hold in a harder regime?")
❌ *"Extend the paper's method to a harder regime and check whether its pattern still holds."* — confirming survival of the pattern is verification; no new mechanism. → `incremental` / `borderline`.
✅ Generative repair: *"An a-priori theorem mapping the harder regime's parameter to a provable convergence-rate / conditioning bound."* — a new theorem.

## 4. Foreseeable port (no 奇效)
❌ *"Apply method A to domain B"* where the outcome is foreseeable and no new capability emerges. → `incremental`.
✅ Generative repair: a cross-domain transfer where a capability **neither field had** emerges (领域A→领域B 有奇效) — a valid `new_application` contribution. (This IS a research idea; only the no-new-capability port fails. Do not over-correct into rejecting fusion.)

---
**One-line self-check before writing any idea:** *"When this succeeds, what new artifact exists that did not exist before?"* If the honest answer is "we now know whether X is true / how big X is / what causes X", it is verification — discard it (or find the new mechanism it could seed instead).
