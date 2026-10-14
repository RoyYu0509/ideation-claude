#!/usr/bin/env python3
"""Match website papers against S2 to identify the correct S2 author.

Reads  data/profile/website_papers.json
Writes data/profile/identity_check.json

identity_check.json schema:
  candidate_author_id:   str | null    — most-likely S2 author ID
  candidate_author_name: str | null
  website_count:         int           — papers extracted from personal website
  s2_matched_count:      int           — website papers found in S2
  s2_total_count:        int           — total papers under candidate author on S2
  s2_only_papers:        [{title, year, paperId}]  — on S2 but not on website
  website_only_papers:   [{title, year}]            — on website but not found in S2
  needs_confirmation:    bool          — true → AskUserQuestion gate required
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config, s2_client  # noqa: E402


def _norm_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def _jaccard(a: str, b: str) -> float:
    wa, wb = set(a.split()), set(b.split())
    if not wa and not wb:
        return 1.0
    return len(wa & wb) / len(wa | wb)


def _title_match(t1: str, t2: str, threshold: float) -> bool:
    return _jaccard(_norm_title(t1), _norm_title(t2)) >= threshold


def main() -> int:
    cfg = config.load_config()   # validates config + applies io.* to s2_client
    jaccard = cfg.profile_identity_jaccard
    profile_dir = config.profile_dir()
    website_papers_path = profile_dir / "website_papers.json"
    identity_check_path = profile_dir / "identity_check.json"
    identity_decision_path = profile_dir / "identity_decision.json"

    # ── Load website papers ──────────────────────────────────────────────────
    if not website_papers_path.exists():
        print("[verify_s2_identity] ERROR: website_papers.json not found; run Phase 0a first",
              file=sys.stderr)
        return 1

    raw = json.loads(website_papers_path.read_text(encoding="utf-8"))
    website_papers = raw if isinstance(raw, list) else raw.get("papers", [])

    if not website_papers:
        print("[verify_s2_identity] 0 papers on website — writing empty identity_check", file=sys.stderr)
        identity_check_path.write_text(json.dumps({
            "candidate_author_id": None,
            "candidate_author_name": None,
            "website_count": 0,
            "s2_matched_count": 0,
            "s2_total_count": 0,
            "s2_only_papers": [],
            "website_only_papers": [],
            "needs_confirmation": False,
        }, indent=2))
        return 0

    # ── Paper-level S2 search ────────────────────────────────────────────────
    print(f"[verify_s2_identity] matching {len(website_papers)} website papers against S2 ...",
          file=sys.stderr)

    author_id_votes: Counter = Counter()
    s2_matched_papers: list[dict] = []
    website_only: list[dict] = []

    for wp in website_papers:
        title = (wp.get("title") or "").strip()
        if not title:
            continue
        try:
            results = s2_client.search_by_title(
                title,
                fields=("paperId", "title", "year", "authors"),
            )
        except Exception as e:
            # FAIL LOUD: a failed query is NOT evidence the paper is absent from S2.
            # Recording it as a no-match (website_only) would fabricate a false
            # researcher identity out of a transient S2 rate-limit/outage — the exact
            # silent fallback this pipeline forbids. Abort with a non-zero exit (no
            # identity_check.json written) so the caller fixes the cause and re-runs.
            print(f"[verify_s2_identity] FATAL: S2 title search failed for "
                  f"'{title[:60]}': {e}", file=sys.stderr)
            print("[verify_s2_identity] Cannot verify researcher identity while S2 is "
                  "rate-limited or unreachable. Set S2_API_KEY (free key: "
                  "https://www.semanticscholar.org/product/api) and re-run Phase 0b.",
                  file=sys.stderr)
            return 2

        best: dict | None = None
        best_sim = 0.0
        for r in results:
            sim = _jaccard(_norm_title(r.get("title") or ""), _norm_title(title))
            if sim > best_sim:
                best_sim = sim
                best = r

        if best and best_sim >= jaccard:
            s2_matched_papers.append(best)
            for author in (best.get("authors") or []):
                aid = author.get("authorId") if isinstance(author, dict) else None
                if aid:
                    author_id_votes[aid] += 1
        else:
            website_only.append({"title": title, "year": wp.get("year")})
            print(f"[verify_s2_identity] no S2 match for: '{title[:80]}'", file=sys.stderr)

    # ── Identify candidate author ────────────────────────────────────────────
    if not author_id_votes:
        print("[verify_s2_identity] no candidate author found — all website papers missing from S2",
              file=sys.stderr)
        identity_check_path.write_text(json.dumps({
            "candidate_author_id": None,
            "candidate_author_name": None,
            "website_count": len(website_papers),
            "s2_matched_count": 0,
            "s2_total_count": 0,
            "s2_only_papers": [],
            "website_only_papers": [{"title": wp.get("title"), "year": wp.get("year")}
                                     for wp in website_papers],
            "needs_confirmation": True,
        }, indent=2))
        return 0

    candidate_author_id = author_id_votes.most_common(1)[0][0]
    vote_count = author_id_votes[candidate_author_id]
    print(f"[verify_s2_identity] candidate: {candidate_author_id} ({vote_count}/{len(s2_matched_papers)} matched papers)",
          file=sys.stderr)

    # ── Fetch full S2 author paper list ──────────────────────────────────────
    try:
        author_info = s2_client.author_details(candidate_author_id, fields=("name",))
        candidate_author_name: str | None = author_info.get("name")
    except Exception:
        candidate_author_name = None

    try:
        s2_raw_papers = s2_client.author_papers(
            candidate_author_id,
            fields=("paperId", "title", "year"),
            max_papers=cfg.profile_identity_max_papers,
        )
    except Exception as e:
        # FAIL LOUD (same rule): an empty list here would silently understate the
        # author's S2 record (s2_total_count=0, bogus "perfect match" → gate skipped).
        # Abort rather than write a misleading identity_check.
        print(f"[verify_s2_identity] FATAL: could not fetch candidate author's S2 "
              f"papers: {e}", file=sys.stderr)
        print("[verify_s2_identity] S2 rate-limited or unreachable mid-verification. "
              "Set S2_API_KEY and re-run Phase 0b.", file=sys.stderr)
        return 2

    # ── Compute S2-only papers (on S2 but not on personal website) ───────────
    website_norms = [_norm_title(wp.get("title") or "") for wp in website_papers]
    s2_only: list[dict] = []
    for s2p in s2_raw_papers:
        s2_title = s2p.get("title") or ""
        s2_norm = _norm_title(s2_title)
        if not any(_jaccard(s2_norm, wn) >= jaccard for wn in website_norms):
            s2_only.append({
                "title": s2_title,
                "year": s2p.get("year"),
                "paperId": s2p.get("paperId"),
            })

    s2_matched_count = len(website_papers) - len(website_only)

    # ── Check cached decision (skip gate if already confirmed this author) ───
    needs_confirmation = True
    if identity_decision_path.exists():
        try:
            dec = json.loads(identity_decision_path.read_text(encoding="utf-8"))
            if dec.get("confirmed_author_id") == candidate_author_id:
                needs_confirmation = False
                print("[verify_s2_identity] cached decision matches candidate — gate not needed",
                      file=sys.stderr)
        except Exception:
            pass

    # Perfect match: all website papers found in S2 AND no extra S2 papers
    if not s2_only and not website_only:
        needs_confirmation = False

    result = {
        "candidate_author_id": candidate_author_id,
        "candidate_author_name": candidate_author_name,
        "website_count": len(website_papers),
        "s2_matched_count": s2_matched_count,
        "s2_total_count": len(s2_raw_papers),
        "s2_only_papers": s2_only[:20],
        "website_only_papers": website_only,
        "needs_confirmation": needs_confirmation,
    }

    identity_check_path.write_text(json.dumps(result, indent=2))
    print(
        f"[verify_s2_identity] wrote identity_check.json — "
        f"S2 total={len(s2_raw_papers)}, matched={s2_matched_count}, "
        f"S2-only={len(s2_only)}, website-only={len(website_only)}, "
        f"needs_confirmation={needs_confirmation}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
