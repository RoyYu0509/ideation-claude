"""Per-paper ideation JSON I/O + schema validation.

The arxiv-generate skill writes one JSON per top paper at
    data/ideations/<YYYY-Www>/<arxiv_id>.json
This module is the read side: digest_writer.py + scout_digest.py load
ideations through these helpers; the schema check keeps the renderer's
contract stable when the ideator prompt changes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import config


# `title` (the PAPER's title) added 2026-07-05: downstream consumers (refine's
# /research seed template) need it verbatim; before this they had to
# reconstruct it from prose. Write-strict here; readers stay tolerant of old
# files that lack it.
REQUIRED_TOP = ("arxiv_id", "week", "title", "paper_summary", "why_relevant", "ideas")
REQUIRED_IDEA = (
    "working_title",
    "claim",
    "method_sketch",
    "sharp_falsifier",
)
# Groundedness fields (2026-07-08 redesign): the load-bearing-premise ledger and
# the depended-asset manifest. WRITE-STRICT ONLY (validate_ideation strict_new=True,
# set by save_ideation / ideate_save.py): a NEW ideation cannot ship without them,
# but pre-redesign on-disk JSON (which lacks them) still loads/renders fine.
# v2 (2026-07-11 verified-kill): + falsifier_thresholds / routes_through per idea,
# probe_class (+ criterion when required) per premise row, needed_paths per asset.
REQUIRED_IDEA_GROUNDING = ("load_bearing_premises", "asset_manifest",
                           "falsifier_thresholds", "routes_through")
_PREMISE_ENTRY_REQ = ("premise", "status", "probe_class")  # + source (verified) / probe (unverified) / criterion (required-class)
_ASSET_ENTRY_REQ = ("url", "kind", "status", "evidence", "needed_paths")
_CRITERION_REQ = ("metric", "direction", "threshold", "threshold_src")
# Decoupled ideation (v0.7) renamed thread_connection -> significance_note. Each idea
# must carry one of them; old on-disk JSON (thread_connection) still validates.
EITHER_IDEA = ("significance_note", "thread_connection")
VALID_DEPTH = {"abstract_only", "websearch_used", "pdf_fetched", "landscape_scanned"}

# Pre-v0.7 ideators emitted idea-level `title`/`falsifier`; the canonical schema
# (and both renderers) use `working_title`/`sharp_falsifier`. normalize_ideation
# maps these so stale on-disk JSON still renders its ideas instead of being dropped.
LEGACY_IDEA_ALIASES = {
    "title": "working_title",
    "falsifier": "sharp_falsifier",
}


def ideation_dir(week: str) -> Path:
    """Return data/ideations/<week>/, creating it."""
    p = config.data_dir() / "ideations" / week
    p.mkdir(parents=True, exist_ok=True)
    return p


def ideation_path(week: str, arxiv_id: str) -> Path:
    return ideation_dir(week) / f"{arxiv_id}.json"


class IdeationSchemaError(ValueError):
    """Raised when an ideation JSON does not match the contract."""


def validate_ideation(data: dict[str, Any], context: str = "", strict_new: bool = False) -> None:
    """Raise IdeationSchemaError if `data` is missing required fields.

    Soft contract: extra fields are allowed (forward-compat); missing
    fields fail. `context` is included in the error message — pass the
    file path or arxiv_id when calling.

    strict_new=True (WRITE side only) additionally requires the 2026-07-08
    groundedness fields per idea (REQUIRED_IDEA_GROUNDING) and checks their
    entry shapes. Readers keep the default False so pre-redesign on-disk
    JSON still validates.
    """
    prefix = f"[{context}] " if context else ""
    for key in REQUIRED_TOP:
        if key not in data:
            raise IdeationSchemaError(f"{prefix}missing top-level field '{key}'")
    if not isinstance(data["ideas"], list):
        raise IdeationSchemaError(f"{prefix}'ideas' must be a list, got {type(data['ideas']).__name__}")
    if not data["ideas"]:
        raise IdeationSchemaError(f"{prefix}'ideas' list is empty (need at least 1)")
    for i, idea in enumerate(data["ideas"]):
        if not isinstance(idea, dict):
            raise IdeationSchemaError(f"{prefix}ideas[{i}] is not an object")
        for key in REQUIRED_IDEA:
            if key not in idea:
                raise IdeationSchemaError(f"{prefix}ideas[{i}] missing field '{key}'")
        if not any(k in idea for k in EITHER_IDEA):
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}] missing one of {EITHER_IDEA}"
            )
        if strict_new:
            _validate_grounding(idea, i, prefix)
    depth = data.get("depth_signal")
    if depth is not None and depth not in VALID_DEPTH:
        raise IdeationSchemaError(
            f"{prefix}depth_signal='{depth}' not in {sorted(VALID_DEPTH)}"
        )


def _validate_grounding(idea: dict[str, Any], i: int, prefix: str) -> None:
    """Write-side shape check for the groundedness fields (strict_new=True)."""
    for key in REQUIRED_IDEA_GROUNDING:
        if key not in idea:
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}] missing field '{key}' — every new idea must "
                f"carry its load-bearing-premise ledger and asset manifest "
                f"(see arxiv-generate references/ideation-schema.md)"
            )
    premises = idea["load_bearing_premises"]
    if not isinstance(premises, list) or not premises:
        raise IdeationSchemaError(
            f"{prefix}ideas[{i}].load_bearing_premises must be a non-empty list "
            f"(1-3 entries): if the claim's success depends on nothing about the "
            f"world, it is not a falsifiable research idea"
        )
    for j, p in enumerate(premises):
        if not isinstance(p, dict):
            raise IdeationSchemaError(f"{prefix}ideas[{i}].load_bearing_premises[{j}] must be an object")
        for sk in _PREMISE_ENTRY_REQ:
            if sk not in p:
                raise IdeationSchemaError(f"{prefix}ideas[{i}].load_bearing_premises[{j}] missing '{sk}'")
        status = p["status"]
        if status not in ("verified", "unverified"):
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}].load_bearing_premises[{j}].status='{status}' "
                f"not in ['verified', 'unverified']"
            )
        if status == "verified" and not p.get("source"):
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}].load_bearing_premises[{j}] is 'verified' but has "
                f"no 'source' quote — verified-by-assertion is the failure mode this "
                f"field exists to prevent"
            )
        if status == "unverified" and not p.get("probe"):
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}].load_bearing_premises[{j}] is 'unverified' but has "
                f"no 'probe' — an unverified premise must name the cheap check that "
                f"would test it"
            )
        pc = p["probe_class"]
        if pc not in ("required", "deferrable"):
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}].load_bearing_premises[{j}].probe_class='{pc}' "
                f"not in ['required', 'deferrable']"
            )
        if pc == "required":
            crit = p.get("criterion")
            if not isinstance(crit, dict):
                raise IdeationSchemaError(
                    f"{prefix}ideas[{i}].load_bearing_premises[{j}] is probe_class='required' "
                    f"but has no 'criterion' — a required premise must PRE-REGISTER "
                    f"{{metric, direction, threshold, threshold_src}} for the verifier to execute"
                )
            for ck in _CRITERION_REQ:
                if ck not in crit or (isinstance(crit[ck], str) and not crit[ck].strip()):
                    raise IdeationSchemaError(
                        f"{prefix}ideas[{i}].load_bearing_premises[{j}].criterion missing '{ck}'"
                    )
    # v2: machine-readable falsifier thresholds (each with a src anchor) +
    # premise routing — the anti-silent-relaxation / anti-circularity substrate.
    ths = idea["falsifier_thresholds"]
    if not isinstance(ths, list):
        raise IdeationSchemaError(f"{prefix}ideas[{i}].falsifier_thresholds must be a list")
    for j, t in enumerate(ths):
        if not isinstance(t, dict) or "value" not in t or not str(t.get("src") or "").strip():
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}].falsifier_thresholds[{j}] needs 'value' and a non-empty "
                f"'src' anchor — an unsourced threshold is an invalid falsifier"
            )
    routes = idea["routes_through"]
    if not isinstance(routes, list):
        raise IdeationSchemaError(f"{prefix}ideas[{i}].routes_through must be a list (may be [])")
    valid_ids = {f"P{j + 1}" for j in range(len(premises))}
    for rid in routes:
        if rid not in valid_ids:
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}].routes_through names '{rid}' but premise ids are positional "
                f"{sorted(valid_ids)}"
            )
        row = premises[int(str(rid)[1:]) - 1]
        if row.get("probe_class") != "required":
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}]: falsifier routes through '{rid}' but that premise is not "
                f"probe_class='required' — anything the threshold depends on must be probe-executed"
            )
    assets = idea["asset_manifest"]
    if not isinstance(assets, list):
        raise IdeationSchemaError(f"{prefix}ideas[{i}].asset_manifest must be a list ([] if no external asset is depended on)")
    for j, a in enumerate(assets):
        if not isinstance(a, dict):
            raise IdeationSchemaError(f"{prefix}ideas[{i}].asset_manifest[{j}] must be an object")
        for sk in _ASSET_ENTRY_REQ:
            if sk not in a:
                raise IdeationSchemaError(f"{prefix}ideas[{i}].asset_manifest[{j}] missing '{sk}'")
        if a["status"] not in ("verified_live", "stub_or_empty", "missing", "unverified"):
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}].asset_manifest[{j}].status='{a['status']}' not in "
                f"['verified_live', 'stub_or_empty', 'missing', 'unverified']"
            )
        if not isinstance(a["needed_paths"], list):
            raise IdeationSchemaError(
                f"{prefix}ideas[{i}].asset_manifest[{j}].needed_paths must be a list of globs "
                f"the method_sketch actually depends on (the screener's mechanical kill substrate)"
            )


# ── Evidence sidecar (Step 5b) — WRITE-side gate mirroring validate_ideation ──
# The sidecar previously had no validating writer (plain Write): a malformed
# file was only discovered when the downstream tolerant reader silently
# proceeded WITHOUT evidence. Same discipline as the ideation JSON now.
REQUIRED_EVIDENCE_TOP = (
    "arxiv_id", "week", "pdf_quotes", "websearch_findings",
    "rejected_candidates", "cross_thread_hints",
)
_EVIDENCE_ENTRY_REQ = {
    "pdf_quotes": ("quote", "why_useful"),
    "websearch_findings": ("takeaway",),
    "rejected_candidates": ("working_title", "why_rejected"),
    "cross_thread_hints": ("thread", "connection"),
}


def validate_evidence(data: dict[str, Any], context: str = "") -> None:
    """Loud structural gate for the evidence sidecar (emptiness is a QUALITY
    judgment for the agent/auditor, not enforced here)."""
    prefix = f"[{context}] " if context else ""
    for key in REQUIRED_EVIDENCE_TOP:
        if key not in data:
            raise IdeationSchemaError(f"{prefix}evidence missing required key '{key}'")
    for key, subreq in _EVIDENCE_ENTRY_REQ.items():
        entries = data[key]
        if not isinstance(entries, list):
            raise IdeationSchemaError(f"{prefix}evidence '{key}' must be a list")
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise IdeationSchemaError(f"{prefix}evidence {key}[{i}] must be an object")
            for sk in subreq:
                if sk not in entry:
                    raise IdeationSchemaError(f"{prefix}evidence {key}[{i}] missing '{sk}'")


def normalize_ideation(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with legacy idea-level field names mapped to canonical ones.

    Maps `title`->`working_title` and `falsifier`->`sharp_falsifier` (see
    LEGACY_IDEA_ALIASES) so pre-v0.7 JSON still renders. A canonical key already
    present always wins; missing top-level fields (e.g. paper_summary) are left
    absent for the renderer to handle gracefully. The top-level dict and each
    idea are shallow-copied so the input is not mutated.
    """
    out = dict(data)
    ideas = out.get("ideas")
    if isinstance(ideas, list):
        new_ideas: list[Any] = []
        for idea in ideas:
            if isinstance(idea, dict):
                idea = dict(idea)
                for legacy, canon in LEGACY_IDEA_ALIASES.items():
                    if canon not in idea and legacy in idea:
                        idea[canon] = idea[legacy]
            new_ideas.append(idea)
        out["ideas"] = new_ideas
    return out


def load_ideation(week: str, arxiv_id: str) -> dict[str, Any] | None:
    """Return the validated ideation dict, or None if not yet written."""
    p = ideation_path(week, arxiv_id)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    validate_ideation(data, context=str(p))
    return data


def save_ideation(week: str, arxiv_id: str, data: dict[str, Any]) -> Path:
    """Validate and write the per-paper ideation JSON. Returns the path."""
    # Ensure the canonical fields are set before validating; the ideator
    # may pass an input shape without explicit week/arxiv_id if the prompt
    # carries them.
    data = dict(data)
    data.setdefault("week", week)
    data.setdefault("arxiv_id", arxiv_id)
    validate_ideation(data, context=f"save:{week}/{arxiv_id}", strict_new=True)
    out = ideation_path(week, arxiv_id)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return out


def load_all_ideations(week: str) -> dict[str, dict[str, Any]]:
    """Return {arxiv_id: normalized_ideation} for every parseable JSON in the dir.

    Resilient by design: this is a RENDER path, so it loads best-effort and
    normalizes legacy field names (normalize_ideation) rather than dropping a
    whole paper because one field drifted from the write-side schema. Only files
    that cannot be parsed as JSON, are not an object, or carry no `arxiv_id` are
    skipped (logged to stderr); the renderer detects those via find_ideation_file
    and shows an honest 'corrupted' note with a refined-plan fallback. The strict
    schema contract is enforced where it belongs — on the WRITE side
    (save_ideation / ideate_save.py), not here.
    """
    import sys

    out: dict[str, dict[str, Any]] = {}
    d = config.data_dir() / "ideations" / week
    if not d.exists():
        return out
    for p in sorted(d.glob("*.json")):
        # Skip non-ideation sidecars written into the same dir by the
        # arxiv-scout workflow (v0.3+): evidence-<id>.json and
        # super-synthesis.json. They don't conform to the ideation schema.
        if p.name.startswith("evidence-") or p.name == "super-synthesis.json":
            continue
        # Skip regeneration-round files (<id>-r<N>.json, 2026-07-11 verified-kill):
        # they carry the same ideation schema AND the same arxiv_id, so loading one
        # would overwrite the canonical round-1 <id>.json entry this dict keys on.
        if re.search(r"-r\d+\.json$", p.name):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[ideate_io] unparseable, skipping {p}: {e}", file=sys.stderr)
            continue
        if not isinstance(data, dict) or not data.get("arxiv_id"):
            print(f"[ideate_io] no arxiv_id, skipping {p}", file=sys.stderr)
            continue
        out[data["arxiv_id"]] = normalize_ideation(data)
    return out


def find_ideation_file(week: str, arxiv_id: str) -> Path | None:
    """Path to this paper's ideation JSON on disk, or None.

    Accepts both the canonical `<id>.json` and the legacy `<id>-ideation.json`
    name some writers emitted. Lets the renderer tell 'present but unparseable'
    (corrupted) apart from 'never written' (ideation not run)."""
    d = config.data_dir() / "ideations" / week
    for name in (f"{arxiv_id}.json", f"{arxiv_id}-ideation.json"):
        p = d / name
        if p.exists():
            return p
    return None


def extract_seed(refined_md: str) -> str:
    """Return the '## /research Seed' block of a refined plan, or '' if absent."""
    marker = "## /research Seed"
    idx = refined_md.find(marker)
    if idx == -1:
        return ""
    seed = refined_md[idx + len(marker):].strip()
    if seed.endswith("---"):
        seed = seed[:-3].rstrip()
    return seed


def load_refined_fallback(week: str, arxiv_id: str) -> list[dict[str, str]]:
    """Refined plans for a paper whose ideation JSON is corrupted.

    The refine pass writes one self-contained markdown plan per idea at
    refined/<id>-idea<N>.md; these survive even when the ideation JSON does not.
    Returns [{working_title, seed, plan_md, source}] in idea order so the
    renderer can fall back to real content instead of a bare placeholder."""
    d = config.data_dir() / "ideations" / week / "refined"
    out: list[dict[str, str]] = []
    if not d.exists():
        return out

    def _idx(p: Path) -> int:
        m = re.search(r"-idea(\d+)\.md$", p.name)
        return int(m.group(1)) if m else 0

    for p in sorted(d.glob(f"{arxiv_id}-idea*.md"), key=_idx):
        md = p.read_text(encoding="utf-8")
        wt = ""
        for line in md.splitlines():
            if line.startswith("**Working title:**"):
                wt = line.split("**Working title:**", 1)[1].strip()
                break
        out.append({"working_title": wt, "seed": extract_seed(md),
                    "plan_md": md, "source": p.name})
    return out


def depth_tier_counts(ideations: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Count {tier: n} for a set of loaded ideations. Useful for the
    generation stage's final report."""
    counts = {t: 0 for t in VALID_DEPTH}
    counts["unknown"] = 0
    for data in ideations.values():
        tier = data.get("depth_signal")
        if tier in VALID_DEPTH:
            counts[tier] += 1
        else:
            counts["unknown"] += 1
    return counts
