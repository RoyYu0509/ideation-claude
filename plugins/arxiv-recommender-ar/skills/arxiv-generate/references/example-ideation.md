# Reference output (real shape, hypothetical content)

For a paper introducing soft coarse-graining pooling for MLIPs, a Tier 2
ideation might produce a bold, paper-worthy idea **seeded by the paper itself**:

```json
{
  "arxiv_id": "2605.25710",
  "week": "2026-W22",
  "paper_summary": "MuSE adds a Soft Coarse-Graining Pooling layer to MACE / SO3krates / PaiNN, where each node is a fractional combination of nearby atoms with learnable weights. The headline empirical result is a 12% MAE reduction on multiscale OMat24 splits where rigid pooling fails. The method's interface is a soft fractional atom-to-node assignment matrix, not a hard partition.",
  "why_relevant": "这篇文章推进了原子尺度多尺度建模的前沿；与你的 a/c coupling 方向同处于「尺度桥接界面」这一问题域。",
  "depth_signal": "websearch_used",
  "has_journal_level_idea": true,
  "ideas": [
    {
      "idea_type": "new_direction",
      "contribution_type": "new_theorem",
      "significance_status": "paper_worthy",
      "working_title": "A priori convergence order for learned coarse-graining interfaces",
      "claim": "The effective coarse-graining order of MuSE's soft assignment is determined by the decay rate of its assignment-matrix singular spectrum; a learnable pooling layer can therefore be constrained to guarantee a target a priori convergence order O(h^p), turning an empirical pooling trick into a numerically-analyzable scheme.",
      "method_sketch": "On a 1D atomistic model problem with a known continuum limit, parameterize the soft-assignment singular spectrum and derive the leading interface error term as a function of its decay rate. Baseline: rigid (hard) pooling, which is O(h^1) at the interface. Metric: log-log slope of H^1 interface error vs h. Novel step: prove the spectrum-decay → convergence-order map, then add it as a differentiable constraint during MuSE training and verify the trained model hits the predicted slope.",
      "significance_note": "首次把可学习 pooling 从经验技巧变成有 a priori 收敛阶保证的数值格式——此前文献只有经验 MAE 改进，没有人给出 learned 界面的收敛阶定理（你的 a/c coupling 收敛分析背景使你能切入这一推导）。",
      "sharp_falsifier": "If the trained-model error-vs-h slope deviates from the spectrum-predicted order by more than 0.5 (vs the theoretical O(h^p) target), the spectrum→order map does not control the actual scheme and the claim is refuted.",
      "falsifier_thresholds": [
        { "value": 0.5, "units": "log-log slope deviation",
          "src": "src: half of the O(h^1)→O(h^2) order gap between rigid and target pooling (paper §4.1 rates)" }
      ],
      "routes_through": ["P1"],
      "load_bearing_premises": [
        { "premise": "MuSE's released 1D model problem has a known closed-form continuum limit whose interface error is measurable in H^1 (i.e. the benchmark is constructed from an analytic reference, not a numerical surrogate)",
          "status": "unverified",
          "probe": "extract the model-problem definition from the paper's setup section and confirm the reference solution is analytic; compute the rigid-pooling slope on 3 grid levels",
          "probe_class": "required",
          "criterion": { "metric": "rigid-pooling log-log H^1 slope over 3 grid levels", "direction": ">=",
                         "threshold": 0.9, "threshold_src": "src: O(h^1) theoretical rate for hard pooling, paper §4.1" },
          "consequence_if_false": "the substrate cannot measure convergence order at all — the whole validation plan dies" }
      ],
      "asset_manifest": [
        { "url": "https://github.com/example/muse",
          "kind": "repo", "needed_for": "soft-assignment layer + 1D model problem generator",
          "needed_paths": ["muse/pooling/*.py", "examples/model1d/*"],
          "status": "unverified", "evidence": "declared — screen verifies" }
      ],
      "why_novel_despite_landscape": null
    }
  ]
}
```

(Real output contains 1+ such ideas and a `notes` field. `priority_pick` is
retired — the independent screener ranks candidates.)
