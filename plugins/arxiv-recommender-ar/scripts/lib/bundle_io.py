#!/usr/bin/env python3
"""Schema + validating writer for a candidate's verification bundle
(bundle.json) — the machine SSOT of the 2026-07-11 verified-kill redesign.

A bundle is the four verification artifacts of ONE candidate idea:
  prior_art        — replayable S2 queries + diff table + hit dispositions
  premises         — premise rows with EXECUTED probes (probe_class rules) +
                     falsifier (src-tagged thresholds, routing, limit analysis)
  theory           — typed-step derivation file + per-step check probes
                     (required iff claim_type is theoretical/both)
  assets           — real file listings (asset_listing.py) per depended asset

Design rules this module enforces at WRITE time (write strict, read tolerant):
  • Every referenced evidence file (probe dirs, listings, theory.md) must
    exist on disk relative to the bundle dir — a bundle whose evidence is
    missing is refused, so prose can never stand in for artifacts.
  • Prior art rests on >=2 REPLAYABLE s2_novelty queries — unless the bundle is
    flagged `degraded` (S2 unreachable), where >=2 arxiv_web_fallback queries stand
    in and the flag travels with the bundle as weaker-evidence provenance.
  • Every falsifier threshold carries a non-empty `src` anchor (v1 grammar:
    any non-empty string; TRUTH is checked by the recheck stage by fetching).
  • probe_class rules are structural: a `required` premise row must carry an
    executed probe whose committed PROBE_VERDICT matches its status; any number
    of rows may be `deferred` (verifier-marked, justification required) — each
    one becomes a mandatory Phase-0 kill-or-confirm check downstream.
  • routes_through premises must exist and be probe_class=required — a
    threshold may never route through a merely-deferrable premise. It MAY route
    through a deferred one: that is precisely what Phase-0 then tests.

Validation errors raise BundleSchemaError naming the offending path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1

CLAIM_TYPES = ("theoretical", "empirical", "both")
PROBE_CLASSES = ("required", "deferrable")
PREMISE_STATUSES = ("probed_pass", "probed_fail", "quote_verified", "unverified", "deferred")
ASSET_STATUSES = ("live_verified", "stub_or_empty", "missing")
ARTIFACT_KEYS = ("prior_art", "asset_check", "premise_probe", "derivation_check")
ARTIFACT_VERDICTS = ("pass", "fail", "deferred", "not_applicable")
DISPOSITION_CLASSES = ("rival", "adjacent", "irrelevant")

REQUIRED_TOP = ("schema", "week", "arxiv_id", "candidate_key", "round_born",
                "working_title", "claim", "claim_type", "prior_art", "premises",
                "theory", "assets", "artifacts")


class BundleSchemaError(ValueError):
    """Raised when bundle.json fails validation; message names the field."""


def _err(path: str, msg: str) -> None:
    raise BundleSchemaError(f"{path}: {msg}")


def _need(obj: dict, key: str, path: str):
    if not isinstance(obj, dict) or key not in obj:
        _err(f"{path}.{key}", "missing required field")
    return obj[key]


def _need_str(obj: dict, key: str, path: str) -> str:
    v = _need(obj, key, path)
    if not isinstance(v, str) or not v.strip():
        _err(f"{path}.{key}", "must be a non-empty string")
    return v


def _need_list(obj: dict, key: str, path: str) -> list:
    v = _need(obj, key, path)
    if not isinstance(v, list):
        _err(f"{path}.{key}", "must be a list")
    return v


def read_probe_verdict(probe_dir: Path) -> dict | None:
    """Parse the committed PROBE_VERDICT from a probe dir's stdout.txt (last
    matching line). None when absent/unparseable."""
    out = probe_dir / "stdout.txt"
    if not out.exists():
        return None
    for line in reversed(out.read_text(encoding="utf-8").splitlines()):
        if line.startswith("PROBE_VERDICT:"):
            try:
                return json.loads(line[len("PROBE_VERDICT:"):].strip())
            except json.JSONDecodeError:
                return None
    return None


def _validate_prior_art(pa: dict, path: str) -> None:
    queries = _need_list(pa, "queries", path)
    s2_queries = [q for q in queries if q.get("tool") == "s2_novelty"]
    fb_queries = [q for q in queries if q.get("tool") == "arxiv_web_fallback"]
    # Normally novelty must rest on >=2 REPLAYABLE S2 queries. When S2 itself is
    # down the screener may fall back to searching arXiv directly, which V0 cannot
    # replay — so that bundle must SAY SO (`degraded` + `degraded_reason`) and still
    # carry >=2 real queries. The flag is the price of the exemption: it travels with
    # the bundle so the gate and the reader know this novelty check is weaker.
    if pa.get("degraded"):
        _need_str(pa, "degraded_reason", path)
        if len(s2_queries) + len(fb_queries) < 2:
            _err(f"{path}.queries", "degraded prior-art still needs >=2 queries "
                                    f"(s2_novelty or arxiv_web_fallback), got {len(s2_queries) + len(fb_queries)}")
    elif len(s2_queries) < 2:
        _err(f"{path}.queries", f"needs >=2 s2_novelty queries (replayable), got {len(s2_queries)}. "
                                "If S2 was unreachable, use arxiv_web_fallback queries and set degraded=true "
                                "+ degraded_reason — never relabel a fallback query as s2_novelty.")
    hit_keys: set[str] = set()
    for i, q in enumerate(queries):
        qp = f"{path}.queries[{i}]"
        _need_str(q, "id", qp)
        tool = _need_str(q, "tool", qp)
        if tool == "s2_novelty":
            mode = _need_str(q, "mode", qp)
            if mode == "search":
                _need_str(q, "query", qp)
            elif mode == "related":
                _need_str(q, "arxiv_id", qp)
            else:
                _err(f"{qp}.mode", f"unknown mode '{mode}'")
            hits = _need_list(q, "hits", qp)
            for j, h in enumerate(hits):
                _need_str(h, "title", f"{qp}.hits[{j}]")
                hit_keys.add(_hit_key(h))
        elif tool == "arxiv_web_fallback":
            # S2-down substitute: same adversarial duty, same disposition duty, but
            # NOT replayable — only legal inside a bundle flagged degraded.
            if not pa.get("degraded"):
                _err(f"{qp}.tool", "arxiv_web_fallback is only allowed when prior_art.degraded is true "
                                   "(with degraded_reason naming the S2 failure)")
            _need_str(q, "query", qp)
            _need_str(q, "note", qp)
            hits = _need_list(q, "hits", qp)
            for j, h in enumerate(hits):
                _need_str(h, "title", f"{qp}.hits[{j}]")
                hit_keys.add(_hit_key(h))
        elif tool == "websearch":
            _need_str(q, "query", qp)
            for j, f in enumerate(_need_list(q, "findings", qp)):
                _need_str(f, "url", f"{qp}.findings[{j}]")
                _need_str(f, "takeaway", f"{qp}.findings[{j}]")
        else:
            _err(f"{qp}.tool", f"unknown tool '{tool}'")
    diff = _need_list(pa, "diff_table", path)
    covered: set[str] = set()
    for i, row in enumerate(diff):
        rp = f"{path}.diff_table[{i}]"
        _need_str(row, "rival", rp)
        _need_str(row, "found_by", rp)
        if not isinstance(_need(row, "same_mechanism", rp), bool):
            _err(f"{rp}.same_mechanism", "must be a boolean")
        _need_str(row, "residual_delta", rp)
        _need_str(row, "source_anchor", rp)
        covered.add(_norm_title(row["rival"]))
    disp = _need_list(pa, "dispositions", path)
    for i, d in enumerate(disp):
        dp = f"{path}.dispositions[{i}]"
        _need_str(d, "hit", dp)
        c = _need_str(d, "class", dp)
        if c not in DISPOSITION_CLASSES:
            _err(f"{dp}.class", f"must be one of {DISPOSITION_CLASSES}")
        _need_str(d, "why", dp)
        covered.add(_norm_title(d["hit"]))
    # Coverage: every recorded S2 hit is either a diff-table rival or dispositioned.
    uncovered = [k for k in hit_keys if k not in covered]
    if uncovered:
        _err(f"{path}", f"S2 hits with neither a diff_table row nor a disposition: {sorted(uncovered)[:5]}"
                        " — every recorded hit must be dispositioned (anti-concealment)")


def _hit_key(h: dict) -> str:
    return _norm_title(h.get("arxiv_id") or h.get("title") or "")


def _norm_title(s: str) -> str:
    """Match dispositions/diff rows to hits loosely: by arxiv id when present
    anywhere in the string, else by lowercased title prefix."""
    import re
    m = re.search(r"\d{4}\.\d{4,5}", s)
    if m:
        return m.group(0)
    return "".join(ch for ch in s.lower() if ch.isalnum())[:60]


def _validate_premises(pm: dict, bundle_dir: Path, path: str) -> None:
    rows = _need_list(pm, "rows", path)
    if not rows:
        _err(f"{path}.rows", "at least one premise row is required")
    ids = set()
    for i, r in enumerate(rows):
        rp = f"{path}.rows[{i}]"
        rid = _need_str(r, "id", rp)
        if rid in ids:
            _err(f"{rp}.id", f"duplicate premise id '{rid}'")
        ids.add(rid)
        _need_str(r, "premise", rp)
        _need_str(r, "consequence_if_false", rp)
        pc = _need_str(r, "probe_class", rp)
        if pc not in PROBE_CLASSES:
            _err(f"{rp}.probe_class", f"must be one of {PROBE_CLASSES}")
        st = _need_str(r, "status", rp)
        if st not in PREMISE_STATUSES:
            _err(f"{rp}.status", f"must be one of {PREMISE_STATUSES}")
        if st == "deferred":
            if pc != "required":
                _err(f"{rp}.status", "deferred only applies to required-class rows "
                                     "(a deferrable row just stays unverified)")
            _need_str(r, "deferred_justification", rp)
        if pc == "required" and st not in ("probed_pass", "probed_fail", "deferred"):
            _err(f"{rp}.status", "required-class premise must be probed_pass/probed_fail "
                                 "(executed probe) or verifier-deferred — prose statuses are not allowed")
        if st in ("probed_pass", "probed_fail"):
            probe = _need(r, "probe", rp)
            pid = _need_str(probe, "id", f"{rp}.probe")
            pdir = bundle_dir / _need_str(probe, "dir", f"{rp}.probe")
            crit = _need(probe, "criterion", f"{rp}.probe")
            for k in ("metric", "direction", "threshold_src"):
                _need_str(crit, k, f"{rp}.probe.criterion")
            if "threshold" not in crit:
                _err(f"{rp}.probe.criterion.threshold", "missing required field")
            if not (pdir / "probe.py").exists():
                _err(f"{rp}.probe.dir", f"probe.py not found on disk: {pdir}")
            verdict = read_probe_verdict(pdir)
            if verdict is None:
                _err(f"{rp}.probe.dir", f"no committed PROBE_VERDICT in {pdir}/stdout.txt "
                                        "— run it via bin/probe_run.sh first")
            if bool(verdict.get("pass")) != (st == "probed_pass"):
                _err(f"{rp}.status", f"status '{st}' contradicts the committed PROBE_VERDICT "
                                     f"(pass={verdict.get('pass')}) in {pdir}/stdout.txt")
            if verdict.get("id") != pid:
                _err(f"{rp}.probe.id", f"probe id '{pid}' != committed verdict id '{verdict.get('id')}'")
        if st == "quote_verified":
            q = _need(r, "quote", rp)
            _need(q, "page", f"{rp}.quote")
            _need_str(q, "text", f"{rp}.quote")
    # No cap on deferred rows (was MAX_DEFERRED=1 until 2026-09). The cap forced
    # the verifier to settle instrument-grade premises with a self-written toy
    # inside a 600s budget, and toy verdicts killed 6 of 18 W35 directions. Each
    # deferred row becomes a mandatory Phase-0 check + two-sided §4 K criterion,
    # so deferring is a stronger fate than a toy probe, not an escape hatch.

    fal = _need(pm, "falsifier", path)
    _need_str(fal, "statement", f"{path}.falsifier")
    ths = _need_list(fal, "thresholds", f"{path}.falsifier")
    for i, t in enumerate(ths):
        tp = f"{path}.falsifier.thresholds[{i}]"
        if "value" not in t:
            _err(f"{tp}.value", "missing required field")
        _need_str(t, "src", tp)  # v1 grammar: non-empty anchor; recheck fetches it
    routes = _need_list(fal, "routes_through", f"{path}.falsifier")
    by_id = {r["id"]: r for r in rows}
    for rid in routes:
        if rid not in by_id:
            _err(f"{path}.falsifier.routes_through", f"unknown premise id '{rid}'")
        if by_id[rid]["probe_class"] != "required":
            _err(f"{path}.falsifier.routes_through",
                 f"premise '{rid}' is routed through by the falsifier but is not probe_class=required "
                 "— anything the threshold depends on must be probe-executed (anti-circularity)")
    la = _need(fal, "limit_analysis", f"{path}.falsifier")
    for k in ("can_trigger", "can_fail_to_trigger", "non_circular"):
        _need_str(la, k, f"{path}.falsifier.limit_analysis")

    for i, d in enumerate(pm.get("rescope_declarations") or []):
        dp = f"{path}.rescope_declarations[{i}]"
        _need(d, "round", dp)
        _need_str(d, "what_changed", dp)
        for rid in _need_list(d, "newly_load_bearing", dp):
            if rid not in by_id:
                _err(f"{dp}.newly_load_bearing", f"unknown premise id '{rid}'")
        _need_list(d, "probes_added", dp)


def _validate_theory(th, claim_type: str, bundle_dir: Path, path: str) -> None:
    if claim_type == "empirical":
        return  # theory may be null
    if not isinstance(th, dict):
        _err(path, f"claim_type '{claim_type}' requires a theory artifact (typed-step derivation)")
    p = bundle_dir / _need_str(th, "path", path)
    if not p.exists():
        _err(f"{path}.path", f"derivation file not found on disk: {p}")
    for i, c in enumerate(_need_list(th, "checks", path)):
        cp = f"{path}.checks[{i}]"
        _need_str(c, "step", cp)
        cdir = bundle_dir / _need_str(c, "probe_dir", cp)
        if not (cdir / "probe.py").exists():
            _err(f"{cp}.probe_dir", f"check probe.py not found on disk: {cdir}")
        if read_probe_verdict(cdir) is None:
            _err(f"{cp}.probe_dir", f"no committed PROBE_VERDICT in {cdir}/stdout.txt")


def _validate_assets(assets: list, bundle_dir: Path, path: str) -> None:
    for i, a in enumerate(assets):
        ap = f"{path}[{i}]"
        _need_str(a, "url", ap)
        _need_str(a, "kind", ap)
        _need_str(a, "needed_for", ap)
        _need_list(a, "needed_paths", ap)
        lst = bundle_dir / _need_str(a, "listing", ap)
        if not lst.exists():
            _err(f"{ap}.listing", f"listing file not found on disk: {lst} "
                                  "— fetch it via bin/asset_listing.sh first")
        st = _need_str(a, "status", ap)
        if st not in ASSET_STATUSES:
            _err(f"{ap}.status", f"must be one of {ASSET_STATUSES}")
        if st != "live_verified" and not (a.get("fallback") or "").strip():
            _err(f"{ap}.fallback", "a non-live asset needs an explicit fallback "
                                   "(reimplement from spec / contact authors / different substrate)")


def validate_bundle(data: dict, bundle_dir: Path | str) -> None:
    """Full write-time validation. Raises BundleSchemaError on first failure."""
    bundle_dir = Path(bundle_dir)
    for k in REQUIRED_TOP:
        if k not in data:
            _err(k, "missing required top-level field")
    if data["schema"] != SCHEMA_VERSION:
        _err("schema", f"expected {SCHEMA_VERSION}, got {data['schema']}")
    ct = data["claim_type"]
    if ct not in CLAIM_TYPES:
        _err("claim_type", f"must be one of {CLAIM_TYPES}")
    if not str(data["claim"]).strip():
        _err("claim", "must be a non-empty string (the Verified Claim)")
    _validate_prior_art(data["prior_art"], "prior_art")
    _validate_premises(data["premises"], bundle_dir, "premises")
    _validate_theory(data["theory"], ct, bundle_dir, "theory")
    _validate_assets(data["assets"] or [], bundle_dir, "assets")
    art = data["artifacts"]
    for k in ARTIFACT_KEYS:
        v = _need(art, k, "artifacts")
        if v not in ARTIFACT_VERDICTS:
            _err(f"artifacts.{k}", f"must be one of {ARTIFACT_VERDICTS}")
    if ct == "empirical" and art["derivation_check"] not in ("not_applicable",):
        pass  # an empirical claim MAY still carry arithmetic checks; not an error
    if ct != "empirical" and art["derivation_check"] == "not_applicable":
        _err("artifacts.derivation_check",
             f"claim_type '{ct}' requires a derivation check (cannot be not_applicable)")


def load_bundle(bundle_dir: Path | str) -> dict:
    """Read-tolerant load: parse bundle.json, no re-validation (V0 re-validates
    explicitly as its structural gate)."""
    p = Path(bundle_dir) / "bundle.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    """CLI validating writer (mirror of ideate_save.py):
    bundle_io.py --in DRAFT.json --bundle-dir DIR
    Validates against disk and writes DIR/bundle.json. Exit 0 = written,
    1 = schema failure (reason on stderr), 2 = usage/IO."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", type=Path, required=True)
    ap.add_argument("--bundle-dir", type=Path, required=True)
    args = ap.parse_args()
    if not args.infile.exists():
        print(f"[bundle_io] draft not found: {args.infile}", file=sys.stderr)
        return 2
    try:
        with open(args.infile, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[bundle_io] FAIL — draft is not valid JSON: {e}", file=sys.stderr)
        return 1
    try:
        validate_bundle(data, args.bundle_dir)
    except BundleSchemaError as e:
        print(f"[bundle_io] FAIL — {e}\n  Fix the named field/evidence file and rerun; "
              f"nothing was written.", file=sys.stderr)
        return 1
    out = args.bundle_dir / "bundle.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
