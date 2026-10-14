#!/usr/bin/env python3
"""Deterministic driver for the arxiv-ideation verified-kill loop — ZERO LLM tokens.

WHY THIS EXISTS (2026-07-12). workflows/arxiv-ideation.js is a Workflow-DSL spec: a round
loop of generate → screen → verify(+V0) → recheck with a candidate/paper STATE MACHINE
(promote / kill / bounce / converge) and a `persistLedger()` after every stage. But the JS
depends on node fs/child_process, so it cannot run in the Workflow sandbox — /arxiv-scout-beta
ENACTS it by hand with a headless L1 subagent. Hand-enactment dropped two things:
  1. the deterministic side-effect `persistLedger()` → NO week-<W>-ideation-ledger.json on disk
     → no crash-resume, no /learn ledger, and the whole candidate state lived only in the
     orchestrator's growing context, which it then approximated from memory (unbounded verify
     retry spins, mis-tracked rounds);
  2. the promote/kill/bounce/converge DECISIONS became LLM judgment instead of code.

This driver OWNS the ledger and every state transition (mirroring exp_ledger.py's "code owns
the state, the LLM only produces verdict strings"). The orchestrator's ideation loop becomes:
    init → per round: begin-round → [worklist→spawn→apply]* → settle → finalize
It spawns ONLY the batches `worklist` prints and pipes the awaited returns back via `apply-*`.
It never tracks candidate state itself. verify_bundle.py (V0) is invoked HERE, so the
verified/bounce/kill branch is code, not an enactor's guess.

Ledger schema is IDENTICAL to the JS (schema:2) so scout_digest.py / scout_web.py still render it.

    run_py.sh scripts/ideation_ledger.py init          --week <W> --gated-pool <path>
    run_py.sh scripts/ideation_ledger.py begin-round    --week <W> --round R
    run_py.sh scripts/ideation_ledger.py worklist        --week <W> --round R --stage {generate|screen|verify|recheck}
    run_py.sh scripts/ideation_ledger.py apply-generate  --week <W> --round R --result <file>
    run_py.sh scripts/ideation_ledger.py apply-screen    --week <W> --round R --result <file>
    run_py.sh scripts/ideation_ledger.py apply-verify    --week <W> --round R --result <file> [--bounce]
    run_py.sh scripts/ideation_ledger.py apply-recheck   --week <W> --round R --result <file>
    run_py.sh scripts/ideation_ledger.py settle          --week <W> --round R
    run_py.sh scripts/ideation_ledger.py finalize        --week <W>

Every subcommand prints a compact JSON status to stdout and persists the ledger. `worklist`
prints the spawn list; an EMPTY list means "skip this stage / advance".
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config  # noqa: E402

# `asset_dead` is retained for ledgers written before 2026-09 only; the screen
# stage no longer mints it (an unavailable asset is recorded with a fallback and
# flows to the spec as a scope constraint).
KILL_REASONS = ["scooped", "premise_failed", "proof_broken", "asset_dead",
                "insignificant", "retread", "integrity_violation", "unspecified"]
# V0 failure codes a producer rewrite can fix (bounce once); everything else KILLS.
# Matches arxiv-ideation.js runV0 MECHANICAL_CODES.
MECHANICAL_CODES = {"schema", "no_committed_verdict", "replay_no_verdict",
                    "prev_unreadable", "ideas_unreadable", "replay_crashed", "v0_no_output"}

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


# ───────────────────────── ledger IO + knobs ──────────────────────────────────────────
def _knobs():
    raw = config.load_config().raw
    scout = raw["scout"]
    return {
        "rounds_max": int(scout["ideation_rounds_max"]),
        "candidates_per_round": int(scout["candidates_per_round"]),
        "verify_fanout": int(scout["verify_fanout"]),
        "survivor_target": int(scout["survivor_target"]),
    }


def _ledger_path(week: str, override: str | None = None) -> Path:
    return Path(override) if override else config.cache_dir() / f"week-{week}-ideation-ledger.json"


def _load(path: Path, week: str) -> dict:
    if path.exists():
        try:
            prev = json.loads(path.read_text())
            if prev.get("week") == week and prev.get("schema") == 2 and "papers" in prev:
                return prev
        except Exception:
            pass  # corrupt → start fresh (never crash on resume material), mirrors the JS
    return {"week": week, "schema": 2, "papers": {}}


def _save(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False))


def _paper_state(ledger: dict, arxiv_id: str) -> dict:
    ps = ledger["papers"].get(arxiv_id)
    if ps is None:
        ps = {"status": "active", "rounds_done": 0, "next_candidate_index": 0,
              "exhaustion_note_zh": None, "candidates": {}, "graveyard": []}
        ledger["papers"][arxiv_id] = ps
    return ps


def _cands(ps: dict, *statuses: str):
    return [(k, c) for k, c in ps["candidates"].items() if c["status"] in statuses]


def _converged_count(ps: dict) -> int:
    return len(_cands(ps, "converged"))


def _mint_certificate(ps: dict, key: str, stage: str, verdict: dict, arxiv_id: str, rnd: int) -> None:
    c = ps["candidates"][key]
    reason = verdict.get("kill_reason")
    cert = {
        "cert_id": f"{arxiv_id}:{key}:r{rnd}",
        "direction": verdict.get("direction") or c.get("direction") or c.get("working_title") or "",
        "direction_zh": verdict.get("direction_zh") or c.get("direction_zh") or "",
        # An unrecognised reason means the producer returned something we do not
        # model — NOT that it faked evidence. Coercing to integrity_violation
        # turns "unknown" into an accusation of fraud; use a neutral bucket.
        "kill_reason": reason if reason in KILL_REASONS else "unspecified",
        "stage": stage,
        "evidence": verdict.get("kill_evidence") or "",
        "evidence_path": verdict.get("evidence_path"),
        "dead_belief": verdict.get("dead_belief"),
        "regeneration_constraint": verdict.get("regeneration_constraint"),
        "round": rnd, "certified_by": stage,
        "retread_of": verdict.get("retread_of"),
    }
    c["status"] = "killed"
    c["death"] = cert
    ps["graveyard"].append(cert)


def _pruned(week: str, arxiv_id: str, key: str) -> bool:
    """Optional owner quality-gate pruning (week-<W>-quality-gate-decision.json), mirrors the JS."""
    p = config.cache_dir() / f"week-{week}-quality-gate-decision.json"
    if not p.exists():
        return False
    try:
        sel = {f"{s['arxiv_id']}:{s['key']}" for s in json.loads(p.read_text()).get("selected_ideas", [])}
    except Exception:
        return False
    return f"{arxiv_id}:{key}" not in sel


def _new_candidate(round_born, file, idea_index, working_title, claim) -> dict:
    return {"round_born": round_born, "file": file, "idea_index": idea_index,
            "working_title": working_title or "", "claim": claim or "",
            "direction": working_title or "", "direction_zh": "",
            "status": "generated", "rank": None, "bundle_dir": None,
            "bounces": {}, "merged_into": None, "artifacts": None,
            "deferred_premises": None, "recheck": None, "refute": None, "error_note": None}


# ───────────────────────── subcommands ─────────────────────────────────────────────────
def cmd_init(led_path, week, args):
    ledger = _load(led_path, week)
    gated = json.loads(Path(args.gated_pool).read_text())
    for p in gated:
        _paper_state(ledger, p["arxiv_id"])   # idempotent: never clobbers an existing paper
    _save(led_path, ledger)
    return {"week": week, "papers": len(ledger["papers"]),
            "active": sum(1 for ps in ledger["papers"].values() if ps["status"] == "active")}


def cmd_begin_round(led_path, week, args):
    """Round-start error requeue: an infra error is not a verdict; requeue to the stage it fell from."""
    ledger = _load(led_path, week)
    requeued = []
    for aid, ps in ledger["papers"].items():
        if ps["status"] != "active":
            continue
        for key, c in _cands(ps, "error"):
            c["status"] = "verified" if "recheck" in (c.get("error_note") or "") else "screened"
            c["error_note"] = None
            requeued.append(f"{aid}:{key}→{c['status']}")
    _save(led_path, ledger)
    active = [aid for aid, ps in ledger["papers"].items() if ps["status"] == "active"]
    return {"round": args.round, "active_papers": active, "requeued": requeued}


def cmd_worklist(led_path, week, args):
    ledger = _load(led_path, week)
    K = _knobs()
    rnd = args.round
    active = [(aid, ps) for aid, ps in ledger["papers"].items() if ps["status"] == "active"]
    items = []

    if args.stage == "generate":
        for aid, ps in active:
            if ps["rounds_done"] >= rnd:            # resume: this round already generated
                continue
            if len(_cands(ps, "generated", "screened", "dormant")) == 0:
                items.append({"arxiv_id": aid, "round": rnd,
                              "regeneration": rnd > 1, "graveyard": ps["graveyard"]})

    elif args.stage == "screen":
        for aid, ps in active:
            fresh = _cands(ps, "generated")
            if fresh:
                items.append({"arxiv_id": aid, "round": rnd, "graveyard": ps["graveyard"],
                              "candidates": [{"key": k, "ideas_file": c["file"], "idea_index": c["idea_index"]}
                                             for k, c in fresh]})

    elif args.stage == "verify":
        # C. PROMOTE (deterministic) then return the candidates to (re)verify.
        for aid, ps in active:
            if _converged_count(ps) >= K["survivor_target"]:
                continue
            in_flight = _cands(ps, "verifying", "verified")
            pool = sorted((c for c in _cands(ps, "screened", "dormant") if not _pruned(week, aid, c[0])),
                          key=lambda kc: (kc[1].get("rank") or 99))
            slots = max(0, K["verify_fanout"] - len(in_flight))
            to_promote = pool[:slots]
            for key, c in pool[len(to_promote):]:
                if c["status"] == "screened":
                    c["status"] = "dormant"
            for key, c in to_promote:
                c["status"] = "verifying"
        _save(led_path, ledger)
        # Return verifying candidates whose bundle isn't composed yet (resume skip).
        for aid, ps in [(a, ledger["papers"][a]) for a, _ in active]:
            for key, c in _cands(ps, "verifying"):
                if c.get("bundle_dir") and (Path(c["bundle_dir"]) / "bundle.json").exists():
                    continue
                items.append({"arxiv_id": aid, "key": key, "round": rnd,
                              "ideas_file": c["file"], "idea_index": c["idea_index"]})

    elif args.stage == "recheck":
        for aid, ps in active:
            for key, c in _cands(ps, "verified"):
                items.append({"arxiv_id": aid, "key": key, "round": rnd,
                              "bundle_dir": c.get("bundle_dir"), "claim": c.get("claim"),
                              "claim_type": c.get("claim_type"), "ideas_file": c["file"],
                              "idea_index": c["idea_index"]})
    else:
        raise SystemExit(f"unknown --stage {args.stage}")

    return {"round": rnd, "stage": args.stage, "count": len(items), "items": items}


def cmd_apply_generate(led_path, week, args):
    ledger = _load(led_path, week)
    K = _knobs()
    results = json.loads(Path(args.result).read_text())
    out = []
    for g in results:
        aid = g["arxiv_id"]
        ps = _paper_state(ledger, aid)
        ps["rounds_done"] = args.round
        if not g.get("has_new_directions") or int(g.get("candidate_count") or 0) == 0:
            ps["status"] = "exhausted_honest"
            ps["exhaustion_note_zh"] = g.get("exhaustion_note_zh") or "本轮未能给出真正不同且值得成文的方向。"
            out.append({"arxiv_id": aid, "exhausted_honest": True})
            continue
        try:
            ideas = json.loads(Path(g["output_path"]).read_text()).get("ideas", [])
        except Exception:
            ideas = []
        registered = []
        for idx in range(len(ideas)):
            key = f"c{ps['next_candidate_index']}"
            ps["next_candidate_index"] += 1
            ps["candidates"][key] = _new_candidate(args.round, g["output_path"], idx,
                                                    ideas[idx].get("working_title"), ideas[idx].get("claim"))
            registered.append(key)
        out.append({"arxiv_id": aid, "registered": registered})
    _save(led_path, ledger)
    return {"round": args.round, "applied": out}


def cmd_apply_screen(led_path, week, args):
    ledger = _load(led_path, week)
    results = json.loads(Path(args.result).read_text())
    out = []
    for s in results:
        aid = s["arxiv_id"]
        ps = _paper_state(ledger, aid)
        for r in s.get("results", []):
            key = r.get("key")
            c = ps["candidates"].get(key)
            if not c or c["status"] != "generated":
                continue
            c["direction"] = r.get("direction") or c["direction"]
            c["direction_zh"] = r.get("direction_zh") or ""
            verdict = r.get("verdict")
            if verdict == "kill":
                _mint_certificate(ps, key, "screen", r, aid, args.round)
            elif verdict == "merged" and r.get("merged_into") and r["merged_into"] in ps["candidates"]:
                c["status"] = "merged"
                c["merged_into"] = r["merged_into"]
            else:
                c["status"] = "screened"
                c["rank"] = r.get("rank") or 99
        out.append({"arxiv_id": aid})
    _save(led_path, ledger)
    return {"round": args.round, "applied": [o["arxiv_id"] for o in out]}


def _run_v0(c: dict, rnd: int) -> dict:
    """Invoke verify_bundle.py (V0) and classify the outcome. Mirrors arxiv-ideation.js runV0."""
    bundle_dir = Path(c["bundle_dir"])
    out_path = bundle_dir / f"recheck-r{rnd}.json"
    prev = bundle_dir / "bundle.prev.json"
    cmd = ["python3", str(PLUGIN_ROOT / "scripts" / "verify_bundle.py"),
           "--bundle", str(bundle_dir), "--round", str(rnd),
           "--ideas", c["file"], "--idea-index", str(c["idea_index"])]
    if prev.exists():
        cmd += ["--prev", str(prev)]
    all_pass_exit = False
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        all_pass_exit = True
    except Exception:
        all_pass_exit = False
    try:
        report = json.loads(out_path.read_text())
    except Exception:
        report = None
    if not report:
        return {"all_pass": False, "kind": "mechanical",
                "failures": [{"code": "v0_no_output", "msg": f"verify_bundle produced no {out_path.name}"}],
                "out_path": str(out_path)}
    if all_pass_exit and report.get("all_pass"):
        return {"all_pass": True, "kind": None, "failures": [], "out_path": str(out_path)}
    failures = [f for r in (report.get("artifact_results") or {}).values() for f in (r.get("failures") or [])]
    kind = "mechanical" if failures and all(f.get("code") in MECHANICAL_CODES for f in failures) else "integrity"
    return {"all_pass": False, "kind": kind, "failures": failures, "out_path": str(out_path)}


def cmd_apply_verify(led_path, week, args):
    """Ingest VERIFY returns, then run V0 per surviving candidate → verified / bounce / kill.
    --bounce marks this as the post-bounce pass (no second bounce is granted)."""
    ledger = _load(led_path, week)
    results = {(r["arxiv_id"], r["key"]): r for r in json.loads(Path(args.result).read_text())}
    bounce = args.bounce
    need_bounce, verified, killed, rescoped = [], [], [], []
    for (aid, key), out in results.items():
        ps = _paper_state(ledger, aid)
        c = ps["candidates"].get(key)
        if not c:
            continue
        verdict = out.get("verdict")
        if not verdict or verdict == "error":
            c["status"] = "error"
            c["error_note"] = out.get("error_note") or "verifier returned nothing"
            continue
        c["bundle_dir"] = out.get("bundle_dir") or c.get("bundle_dir")
        c["claim"] = out.get("claim") or c.get("claim")
        c["claim_type"] = out.get("claim_type")
        c["deferred_premises"] = int(out.get("deferred_premises") or 0)
        if verdict == "kill":
            _mint_certificate(ps, key, "verify", out, aid, args.round)
            killed.append(f"{aid}:{key}")
            continue
        if verdict == "rescope":
            # The mechanism stands; the route offered to test it does not exist
            # (wrong-order reference scheme, inapplicable ground truth, asset the
            # route needed). NO certificate and NO regeneration_constraint — the
            # direction is not dead, one path to it is. The candidate stays on
            # disk with its evidence so the human gate can see it.
            c["status"] = "rescoped"
            c["rescope_note"] = out.get("rescope_note") or out.get("kill_evidence") or ""
            rescoped.append(f"{aid}:{key}")
            continue
        # V0 mechanical recheck (code-owned branch).
        if not c.get("bundle_dir"):
            c["status"] = "error"
            c["error_note"] = "verify returned no bundle_dir"
            continue
        v0 = _run_v0(c, args.round)
        if v0["all_pass"]:
            c["status"] = "verified"
            c["v0_path"] = v0["out_path"]
            verified.append(f"{aid}:{key}")
        elif v0["kind"] == "mechanical" and not bounce and not c["bounces"].get("verify"):
            c["bounces"]["verify"] = 1
            try:
                (Path(c["bundle_dir"]) / "bundle.prev.json").write_text(
                    (Path(c["bundle_dir"]) / "bundle.json").read_text())
            except Exception:
                pass
            c["v0_note"] = "\n".join(f"[{f.get('code')}] {f.get('msg')}" for f in v0["failures"])
            need_bounce.append({"arxiv_id": aid, "key": key, "round": args.round,
                                "ideas_file": c["file"], "idea_index": c["idea_index"],
                                "bounce_note": c["v0_note"]})
        else:
            reason = "integrity_violation" if v0["kind"] == "integrity" else "premise_failed"
            evid = ("post-bounce V0 still failing: " if bounce else "") + \
                   "; ".join(f"[{f.get('code')}] {f.get('msg')}" for f in v0["failures"])[:500]
            _mint_certificate(ps, key, "verify",
                              {"kill_reason": reason, "kill_evidence": evid, "evidence_path": v0["out_path"]},
                              aid, args.round)
            killed.append(f"{aid}:{key}")
    _save(led_path, ledger)
    return {"round": args.round, "verified": verified, "killed": killed,
            "rescoped": rescoped,
            "bounce_count": len(need_bounce), "bounce_items": need_bounce}


def cmd_apply_recheck(led_path, week, args):
    """Ingest paired RECHECK + REFUTE returns → converged / killed (significance floor enforced)."""
    ledger = _load(led_path, week)
    K = _knobs()
    results = json.loads(Path(args.result).read_text())
    converged, killed, errored = [], [], []
    for r in results:
        aid, key = r["arxiv_id"], r["key"]
        ps = _paper_state(ledger, aid)
        c = ps["candidates"].get(key)
        if not c:
            continue
        # L4 anti-fabrication (2026-07-12): the CONVERGENCE-critical recheck verdict is read
        # from disk — <bundle_dir>/recheck-semantic.json, written by the recheck leaf ITSELF —
        # in preference to the orchestrator-passed return, so a hand-enacting orchestrator cannot
        # fabricate a paper_worthy+confrontation verdict to force convergence. Falls back to the
        # passed value only if the leaf wrote no file (older skill / infra miss).
        rc, rf = r.get("recheck"), r.get("refute")
        bd = c.get("bundle_dir")
        if bd:
            for fname, target in (("recheck-semantic.json", "rc"), ("refute.json", "rf")):
                try:
                    disk = json.loads((Path(bd) / fname).read_text())
                    if target == "rc":
                        rc = disk
                    else:
                        rf = disk
                except Exception:
                    pass  # no on-disk verdict → keep the passed value
        if not rc or not rf:
            c["status"] = "error"
            c["error_note"] = "recheck/refute agent returned nothing"
            errored.append(f"{aid}:{key}")
            continue
        c["recheck"] = rc
        c["refute"] = {"verdict": rf.get("verdict"), "killing_hit": rf.get("killing_hit"),
                       "queries": rf.get("queries")}
        if rf.get("verdict") == "scooped":
            hit = rf.get("killing_hit") or {}
            evid = f"{hit.get('title')} — {hit.get('why')} ({hit.get('url')})" if hit else "refutation hit"
            _mint_certificate(ps, key, "recheck", {"kill_reason": "scooped", "kill_evidence": evid}, aid, args.round)
            killed.append(f"{aid}:{key}")
            continue
        conf = rc.get("significance_confrontation") or {}
        sig_ok = rc.get("significance") == "paper_worthy" and conf and conf.get("strongest_rival_row")
        if rc.get("verdict") == "kill" or not rc.get("all_artifacts_reconfirmed") or not sig_ok:
            evid = rc.get("kill_evidence") or (
                f"significance={rc.get('significance')} (floor: paper_worthy)"
                if rc.get("significance") != "paper_worthy" else "artifact re-check not reconfirmed")
            _mint_certificate(ps, key, "recheck",
                              {"kill_reason": rc.get("kill_reason") or "insignificant", "kill_evidence": evid,
                               "dead_belief": rc.get("dead_belief"),
                               "regeneration_constraint": rc.get("regeneration_constraint")},
                              aid, args.round)
            killed.append(f"{aid}:{key}")
            continue
        c["status"] = "converged"
        c["artifacts"] = rc.get("artifact_pass")
        converged.append(f"{aid}:{key}")
    # Settle any paper that hit the survivor target this pass (mirrors the JS inline settle).
    for aid, ps in ledger["papers"].items():
        if ps["status"] == "active" and _converged_count(ps) >= K["survivor_target"]:
            ps["status"] = "converged"
            for _, c in _cands(ps, "dormant", "screened"):
                c["status"] = "shelved"
    _save(led_path, ledger)
    return {"round": args.round, "converged": converged, "killed": killed, "errored": errored}


def cmd_settle(led_path, week, args):
    ledger = _load(led_path, week)
    K = _knobs()
    settled = []
    for aid, ps in ledger["papers"].items():
        if ps["status"] == "active" and _converged_count(ps) >= K["survivor_target"]:
            ps["status"] = "converged"
            for _, c in _cands(ps, "dormant", "screened"):
                c["status"] = "shelved"
            settled.append(aid)
    _save(led_path, ledger)
    return {"round": args.round, "settled": settled}


def cmd_finalize(led_path, week, args):
    """Round cap: still-active papers settle as exhausted_budget; emit the ideation manifest."""
    ledger = _load(led_path, week)
    for aid, ps in ledger["papers"].items():
        if ps["status"] == "active":
            ps["status"] = "exhausted_budget"
            for _, c in _cands(ps, "dormant", "screened", "generated", "error", "verifying", "verified"):
                if c["status"] != "error":
                    c["status"] = "shelved"
    _save(led_path, ledger)
    manifest = []
    for aid, ps in ledger["papers"].items():
        conv = _cands(ps, "converged")
        manifest.append({
            "arxiv_id": aid, "status": ps["status"], "idea_count": len(conv),
            "has_journal_level_idea": len(conv) > 0,
            "output_path": conv[0][1]["file"] if conv else None,
            "evidence_path": None, "killed_directions": len(ps["graveyard"]),
            "exhaustion_note_zh": ps.get("exhaustion_note_zh"),
            "survivor_key": conv[0][0] if conv else None,
        })
    counts = {}
    for ps in ledger["papers"].values():
        counts[ps["status"]] = counts.get(ps["status"], 0) + 1
    return {"status_counts": counts, "ideation_manifest": manifest}


DISPATCH = {
    "init": cmd_init, "begin-round": cmd_begin_round, "worklist": cmd_worklist,
    "apply-generate": cmd_apply_generate, "apply-screen": cmd_apply_screen,
    "apply-verify": cmd_apply_verify, "apply-recheck": cmd_apply_recheck,
    "settle": cmd_settle, "finalize": cmd_finalize,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=list(DISPATCH))
    ap.add_argument("--week", required=True)
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--stage", default=None)
    ap.add_argument("--result", default=None)
    ap.add_argument("--gated-pool", default=None)
    ap.add_argument("--ledger", default=None, help="override ledger path (default: cache_dir/week-<W>-ideation-ledger.json)")
    ap.add_argument("--bounce", action="store_true")
    args = ap.parse_args()
    led_path = _ledger_path(args.week, args.ledger)
    out = DISPATCH[args.cmd](led_path, args.week, args)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
