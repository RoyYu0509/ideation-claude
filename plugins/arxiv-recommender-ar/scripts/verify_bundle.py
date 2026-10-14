#!/usr/bin/env python3
"""V0 mechanical recheck engine for a candidate's verification bundle —
ZERO LLM tokens. Run by the arxiv-ideation workflow (execSync) BEFORE any
recheck agent is spawned; a bundle that fails its own re-execution bounces
straight back to the producer with the mechanical diff.

    run_py.sh scripts/verify_bundle.py --bundle <dir> --round N
        [--prev <prior bundle.json>] [--out <path>] [--skip-network]
    run_py.sh scripts/verify_bundle.py --bundle <dir> --freshness

Checks (each → {pass, failures[], warnings[]} in the output JSON):
  structural       — bundle_io.validate_bundle re-run (defense in depth) +
                     falsifier routing/threshold-src/deferred-count gates
  premise_probe    — RE-EXECUTE every probe (probe_run.sh --suffix .replay);
                     PROBE_VERDICT fields must reproduce (pass exact, value
                     rtol 1e-6). Hash mismatch is recorded as a warning only —
                     re-execution is the verdict, hashes are same-host
                     tamper evidence.
  derivation_check — same re-execution for theory check probes
  prior_art        — replay every s2_novelty query verbatim. SET-INTERSECTION
                     semantics (S2 index/rank drifts daily): FAIL only when a
                     hit present in BOTH the recorded and replayed result has
                     no diff-table row and no disposition (concealment).
                     Recorded-but-gone → warning; replay-new → handed to the
                     recheck agent via `new_hits`.
  asset_check      — re-fetch every listing; re-evaluate needed_paths + code
                     floor. live_verified recorded but now stub/missing → FAIL.
  drift (--prev)   — falsifier threshold changed with no rescope declaration →
                     threshold_drift FAIL; routes_through grew with no
                     declaration → rescope_without_probe FAIL; every declared
                     newly_load_bearing premise must be probed_pass.
  gen-consistency (--ideas + --idea-index) — the bundle's claim must equal the
                     generator's claim STRING-EXACTLY, and the bundle's
                     falsifier thresholds must match the generator's declared
                     falsifier_thresholds (value+units). The verifier may KILL
                     a candidate; it may never weaken or re-aim it.

--freshness (GATE-1 card info line, NOT a gate): replay the first S2 query +
re-fetch assets; print {new_hits, assets} JSON; always exit 0.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import asset_listing, bundle_io, config, s2_client  # noqa: E402

RTOL = 1e-6


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _result() -> dict:
    return {"pass": True, "failures": [], "warnings": []}


def _fail(res: dict, code: str, msg: str) -> None:
    res["pass"] = False
    res["failures"].append({"code": code, "msg": msg})


def _warn(res: dict, code: str, msg: str) -> None:
    res["warnings"].append({"code": code, "msg": msg})


# ── probes ────────────────────────────────────────────────────────────────────
def _replay_probe(plugin_root: Path, probe_dir: Path, res: dict, label: str) -> None:
    committed = bundle_io.read_probe_verdict(probe_dir)
    if committed is None:
        _fail(res, "no_committed_verdict", f"{label}: no PROBE_VERDICT in {probe_dir}/stdout.txt")
        return
    proc = subprocess.run(
        ["bash", str(plugin_root / "bin" / "probe_run.sh"), str(probe_dir), "--suffix", ".replay"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        _fail(res, "replay_crashed",
              f"{label}: probe re-execution failed (exit {proc.returncode}): "
              f"{(proc.stderr or '').strip()[-300:]}")
        return
    replay_out = probe_dir / "stdout.replay.txt"
    replayed = None
    for line in reversed(replay_out.read_text(encoding="utf-8").splitlines()):
        if line.startswith("PROBE_VERDICT:"):
            try:
                replayed = json.loads(line[len("PROBE_VERDICT:"):].strip())
            except json.JSONDecodeError:
                replayed = None
            break
    if replayed is None:
        _fail(res, "replay_no_verdict", f"{label}: replay produced no PROBE_VERDICT")
        return
    if bool(replayed.get("pass")) != bool(committed.get("pass")):
        _fail(res, "verdict_flip",
              f"{label}: committed pass={committed.get('pass')} but replay pass={replayed.get('pass')} "
              "— committed verdict does not reproduce (integrity event)")
        return
    cv, rv = committed.get("value"), replayed.get("value")
    if isinstance(cv, (int, float)) and isinstance(rv, (int, float)):
        denom = max(abs(cv), abs(rv), 1e-300)
        if abs(cv - rv) / denom > RTOL:
            _fail(res, "value_drift",
                  f"{label}: committed value={cv} vs replay value={rv} exceeds rtol {RTOL}")
    # hashes: same-host tamper evidence only, never the verdict
    meta_p, meta_r = probe_dir / "meta.json", probe_dir / "meta.replay.json"
    try:
        m0 = json.loads(meta_p.read_text())
        m1 = json.loads(meta_r.read_text())
        if m0.get("sha256_script") != m1.get("sha256_script"):
            _fail(res, "script_changed",
                  f"{label}: probe.py hash changed since the committed run (tamper)")
    except (OSError, json.JSONDecodeError):
        _warn(res, "meta_unreadable", f"{label}: meta.json/meta.replay.json unreadable")


# ── prior-art replay ──────────────────────────────────────────────────────────
_ARXIV_RE = re.compile(r"\d{4}\.\d{4,5}")


def _hit_keys(hits: list[dict]) -> dict[str, dict]:
    out = {}
    for h in hits:
        k = h.get("arxiv_id") or None
        if not k:
            t = (h.get("title") or "").lower()
            k = "".join(ch for ch in t if ch.isalnum())[:60]
        if k:
            out[k] = h
    return out


def _covered_keys(pa: dict) -> set[str]:
    keys = set()
    for s in ([r.get("rival", "") for r in pa.get("diff_table", [])]
              + [d.get("hit", "") for d in pa.get("dispositions", [])]):
        m = _ARXIV_RE.search(s)
        keys.add(m.group(0) if m else "".join(ch for ch in s.lower() if ch.isalnum())[:60])
    return keys


def _replay_queries(pa: dict, res: dict, skip_network: bool) -> list[dict]:
    fields = ("paperId", "title", "abstract", "year", "venue", "externalIds")
    new_hits: list[dict] = []
    if skip_network:
        _warn(res, "network_skipped", "prior-art replay skipped (--skip-network)")
        return new_hits
    covered = _covered_keys(pa)
    for q in pa.get("queries", []):
        if q.get("tool") != "s2_novelty":
            continue  # websearch findings are the RECHECK agent's WebFetch job
        try:
            if q.get("mode") == "search":
                raw = s2_client.search_by_title(q["query"], fields=fields,
                                                limit=int(q.get("limit", 8)))
            else:
                raw = s2_client.recommendations_for_paper(
                    f"ArXiv:{q['arxiv_id']}", fields=fields, limit=int(q.get("limit", 8)))
        except Exception as e:  # network failure ≠ producer failure
            _warn(res, "replay_unavailable", f"{q.get('id')}: S2 replay failed ({e})")
            continue
        replay = _hit_keys([{
            "title": p.get("title") or "",
            "arxiv_id": (p.get("externalIds") or {}).get("ArXiv"),
            "year": p.get("year"),
        } for p in raw])
        recorded = _hit_keys(q.get("hits", []))
        both = set(replay) & set(recorded)
        concealed = [k for k in both if k not in covered]
        if concealed:
            _fail(res, "hit_concealed",
                  f"{q.get('id')}: hit(s) present in BOTH recorded and replayed results but "
                  f"never dispositioned: {sorted(concealed)[:5]} — every hit needs a diff-table "
                  "row or a disposition")
        for k in set(recorded) - set(replay):
            _warn(res, "hit_gone", f"{q.get('id')}: recorded hit '{k}' absent from replay (S2 drift)")
        for k in set(replay) - set(recorded):
            new_hits.append({"query_id": q.get("id"), **replay[k]})
    return new_hits


# ── assets ────────────────────────────────────────────────────────────────────
def _recheck_assets(assets: list[dict], bundle_dir: Path, res: dict,
                    skip_network: bool) -> list[dict]:
    statuses = []
    if skip_network:
        _warn(res, "network_skipped", "asset re-fetch skipped (--skip-network)")
        return statuses
    for a in assets:
        try:
            listing = asset_listing.fetch_listing(a["url"])
        except Exception as e:
            _warn(res, "asset_unavailable", f"{a['url']}: re-fetch failed ({e})")
            continue
        ev = asset_listing.evaluate(listing, a.get("needed_paths") or [])
        statuses.append({"url": a["url"], "recorded": a.get("status"), "now": ev["status"],
                         "reason": ev.get("reason")})
        if a.get("status") == "live_verified" and ev["status"] != "live_verified":
            # WARNING, not a failure. A re-fetch disagreeing with the recorded
            # status means the world changed or the listing tool is wrong — it is
            # not evidence the producer faked anything. This fired as
            # `integrity_violation` on 2608.22504-c0 in W35: the HuggingFace path
            # under-reported every LFS file as 0 bytes, the screener had caught
            # that and filed a corrected listing, and V0 re-ran the same broken
            # tool and called the correction fraud. The status change is recorded
            # in `assets_now` either way; assets no longer kill candidates.
            _warn(res, "asset_regressed",
                  f"{a['url']}: recorded live_verified but re-fetch says {ev['status']} "
                  f"({ev.get('reason')}) — verify against the bundle's own asset notes "
                  f"before treating this as real; listing tools can be wrong")
    return statuses


# ── generator-consistency (anti-weakening) ────────────────────────────────────
def _check_gen_consistency(cur: dict, ideas_path: Path, idea_index: int, res: dict) -> None:
    try:
        gen = json.loads(ideas_path.read_text(encoding="utf-8"))
        idea = (gen.get("ideas") or [])[idea_index]
    except (OSError, json.JSONDecodeError, IndexError) as e:
        _fail(res, "ideas_unreadable", f"cannot read ideas[{idea_index}] from {ideas_path}: {e}")
        return
    if (cur.get("claim") or "").strip() != (idea.get("claim") or "").strip():
        _fail(res, "claim_drift",
              "bundle claim differs from the generator's claim — the verifier may kill a "
              "candidate but never re-aim it. Bundle claim must be the ideas-file claim verbatim.")
    gen_th = [(t.get("value"), t.get("units")) for t in (idea.get("falsifier_thresholds") or [])]
    cur_th = [(t.get("value"), t.get("units")) for t in
              cur["premises"]["falsifier"].get("thresholds", [])]
    if gen_th and gen_th != cur_th:
        _fail(res, "threshold_drift",
              f"bundle falsifier thresholds {cur_th} differ from the generator's declared "
              f"{gen_th} with no legitimate channel — silent weakening/re-anchoring")


# ── drift vs prior round ──────────────────────────────────────────────────────
def _check_drift(cur: dict, prev: dict, res: dict) -> None:
    cf, pf = cur["premises"]["falsifier"], prev["premises"]["falsifier"]
    decls = cur["premises"].get("rescope_declarations") or []
    declared_change = bool(decls)
    cur_th = [(t.get("value"), t.get("units")) for t in cf.get("thresholds", [])]
    prev_th = [(t.get("value"), t.get("units")) for t in pf.get("thresholds", [])]
    if cur_th != prev_th and not declared_change:
        _fail(res, "threshold_drift",
              f"falsifier thresholds changed {prev_th} -> {cur_th} with NO rescope declaration "
              "— silent goalpost move")
    grew = set(cf.get("routes_through", [])) - set(pf.get("routes_through", []))
    if grew:
        declared = set()
        for d in decls:
            declared |= set(d.get("newly_load_bearing", []))
        undeclared = grew - declared
        if undeclared:
            _fail(res, "rescope_without_probe",
                  f"falsifier now routes through {sorted(undeclared)} with no rescope declaration")
    by_id = {r["id"]: r for r in cur["premises"]["rows"]}
    for d in decls:
        for rid in d.get("newly_load_bearing", []):
            row = by_id.get(rid)
            if not row or row.get("status") != "probed_pass":
                _fail(res, "rescope_without_probe",
                      f"rescope declares '{rid}' newly load-bearing but it is not probed_pass "
                      "— a re-scope closes only through an EXECUTED passing probe")


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, required=True, help="bundle dir (holds bundle.json)")
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--prev", type=Path, default=None, help="prior bundle.json snapshot for drift gates (bounce rewrites)")
    ap.add_argument("--ideas", type=Path, default=None, help="generator's ideation JSON for claim/threshold consistency")
    ap.add_argument("--idea-index", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--skip-network", action="store_true")
    ap.add_argument("--freshness", action="store_true",
                    help="GATE-1 info mode: first-query replay + asset re-fetch only; always exit 0")
    args = ap.parse_args()

    plugin_root = config.plugin_root()
    # load_config() runs lib.runtime.apply, which injects the S2 knobs into
    # s2_client. Without it every prior-art replay raises "s2_client is
    # unconfigured", gets swallowed as a replay_unavailable warning, and the
    # novelty re-check silently verifies nothing (2026-W35: every recheck).
    if not args.skip_network:
        config.load_config()
    bundle_dir = args.bundle.resolve()
    try:
        data = bundle_io.load_bundle(bundle_dir)
    except (OSError, json.JSONDecodeError) as e:
        print(f"verify_bundle: cannot read {bundle_dir}/bundle.json: {e}", file=sys.stderr)
        return 2

    if args.freshness:
        res = _result()
        pa = dict(data.get("prior_art") or {})
        pa["queries"] = (pa.get("queries") or [])[:1]
        new_hits = _replay_queries(pa, res, skip_network=False)
        assets = _recheck_assets(data.get("assets") or [], bundle_dir, res, skip_network=False)
        print(json.dumps({"bundle": str(bundle_dir), "checked_utc": _utc(),
                          "new_hits": new_hits, "assets": assets,
                          "warnings": res["warnings"]}, ensure_ascii=False))
        return 0

    results = {k: _result() for k in
               ("structural", "premise_probe", "derivation_check", "prior_art", "asset_check")}

    # structural (defense in depth: writer already validated, V0 re-validates)
    try:
        bundle_io.validate_bundle(data, bundle_dir)
    except bundle_io.BundleSchemaError as e:
        _fail(results["structural"], "schema", str(e))

    # probe re-execution
    if results["structural"]["pass"]:
        for r in data["premises"]["rows"]:
            if r.get("status") in ("probed_pass", "probed_fail"):
                _replay_probe(plugin_root, bundle_dir / r["probe"]["dir"],
                              results["premise_probe"], f"premise {r['id']}")
        th = data.get("theory")
        if isinstance(th, dict):
            for c in th.get("checks", []):
                _replay_probe(plugin_root, bundle_dir / c["probe_dir"],
                              results["derivation_check"], f"theory {c['step']}")
        new_hits = _replay_queries(data["prior_art"], results["prior_art"], args.skip_network)
        asset_now = _recheck_assets(data.get("assets") or [], bundle_dir,
                                    results["asset_check"], args.skip_network)
    else:
        new_hits, asset_now = [], []

    if args.prev:
        try:
            prev = json.loads(args.prev.read_text(encoding="utf-8"))
            _check_drift(data, prev, results["structural"])
        except (OSError, json.JSONDecodeError) as e:
            _fail(results["structural"], "prev_unreadable", f"cannot read --prev bundle: {e}")
    if args.ideas is not None and args.idea_index is not None:
        _check_gen_consistency(data, args.ideas, args.idea_index, results["structural"])

    all_pass = all(r["pass"] for r in results.values())
    out = {
        "schema": 1, "round": args.round, "bundle": str(bundle_dir),
        "generated_utc": _utc(), "all_pass": all_pass,
        "artifact_results": results, "new_hits": new_hits, "assets_now": asset_now,
    }
    out_path = args.out or (bundle_dir / f"recheck-r{args.round}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps({"all_pass": all_pass, "out": str(out_path),
                      "failed": [k for k, r in results.items() if not r["pass"]]}))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
