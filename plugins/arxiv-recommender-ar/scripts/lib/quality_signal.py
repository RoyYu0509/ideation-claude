"""Publication-time quality signal — author prior, paper influence, repo validity.

UNLIKE :mod:`citation_signal`, this module does NOT produce a ranked list that
feeds RRF fusion. Mixing a blunt quality score into fusion is exactly the
mistake that the (disabled) category-rebalance signal made — it displaced the
top relevance pick and tanked dp@1. Instead this is a STAGED *annotate* layer:
:func:`annotate` returns ``{arxiv_id: QualityAnnotation}`` and the caller stamps
the fields onto each candidate. The Claude reranker then reads them as a
*tiebreaker* — never an override of profile-fit.

Three orthogonal signals, all available at publication time (when citation
count is still ~0):

* **author prior** — max/median author h-index + citation count (S2 batch).
* **paper influence** — the paper's own citationCount / influentialCitationCount
  (usually 0 for brand-new, informative for fast movers) + venue.
* **repo validity** — if the paper *claims* a GitHub repo, is it real and
  non-empty? ``repo_active`` (mild +), ``repo_claimed_but_dead`` (penalize),
  ``no_repo`` / ``repo_unverifiable`` (NEUTRAL — many excellent theory papers
  legitimately ship no code; rate-limits and network errors must never be read
  as "dead").

Domain guardrail: the ONLY negative tier is ``repo_claimed_but_dead``. A paper
with no code link, or a non-GitHub host, or an unverifiable repo, is never
demoted below ``neutral``.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from . import s2_client

# ── Repo URL extraction ─────────────────────────────────────────────────────
# Greedy path capture; trailing punctuation / ``.git`` stripped in _clean_repo
# so a sentence-final URL ("...github.com/org/Repo.") doesn't eat the period
# while a legitimate dotted repo name ("org/repo.js") survives.
GITHUB_URL_RE = re.compile(r"https?://github\.com/([\w.-]+)/([\w.-]+)", re.I)
# Other code/data hosts we recognise but do NOT verify → repo_unverifiable
# (so they are never mis-labelled no_repo and never penalised).
OTHER_HOST_RE = re.compile(
    r"https?://(gitlab\.com|bitbucket\.org|zenodo\.org|codeberg\.org|huggingface\.co)/\S+",
    re.I,
)
_TRAILING = ".,;:)]}>\"'"

# Operational knob — injected from config.yaml io.github_timeout via
# lib.runtime.apply (called by config.load_config()). None until applied.
GITHUB_TIMEOUT_S: int | None = None

# Repo status constants
REPO_ACTIVE = "repo_active"
REPO_DEAD = "repo_claimed_but_dead"
REPO_NONE = "no_repo"
REPO_UNVERIFIABLE = "repo_unverifiable"

# Quality tiers
TIER_STRONG = "strong"
TIER_NEUTRAL = "neutral"
TIER_WEAK = "weak"

_S2_FIELDS = [
    "paperId",
    "externalIds",
    "citationCount",
    "influentialCitationCount",
    "venue",
    "publicationVenue",
    "authors.hIndex",
    "authors.citationCount",
]


@dataclass
class QualityAnnotation:
    # author prior
    author_h_max: int | None = None
    author_h_median: float | None = None
    author_cite_max: int | None = None
    # paper influence
    paper_citation_count: int | None = None
    influential_citation_count: int | None = None
    venue: str | None = None
    venue_type: str | None = None  # 'journal' | 'conference' | None
    # repo
    repo_url: str | None = None
    repo_host: str | None = None  # 'github' | 'gitlab' | ... | None
    repo_status: str = REPO_NONE
    repo_stars: int | None = None
    repo_pushed_at: str | None = None
    # rollups for downstream consumers
    quality_tier: str = TIER_NEUTRAL
    quality_flags: list[str] = field(default_factory=list)


# ── Pure helpers (no network — unit-testable) ───────────────────────────────

def _clean_repo(owner: str, repo: str) -> tuple[str, str]:
    repo = repo.rstrip(_TRAILING)
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    repo = repo.rstrip(_TRAILING)
    return owner.rstrip(_TRAILING), repo


def extract_repo_url(candidate: dict[str, Any]) -> tuple[str | None, str | None, list[str]]:
    """Return (repo_url, host, flags). host is 'github' for a verifiable repo,
    or 'gitlab'/'zenodo'/... for a recognised-but-unverifiable host, or None.

    Looks in ``comment`` → ``links`` → ``abstract`` (first two are only present
    if arxiv_client was extended to keep them; falls back to abstract otherwise).
    """
    flags: list[str] = []
    haystacks: list[str] = []
    for key in ("comment", "abstract"):
        v = candidate.get(key)
        if isinstance(v, str) and v:
            haystacks.append(v)
    links = candidate.get("links")
    if isinstance(links, (list, tuple)):
        haystacks.extend(str(x) for x in links if x)

    gh: list[tuple[str, str]] = []
    for text in haystacks:
        for m in GITHUB_URL_RE.finditer(text):
            owner, repo = _clean_repo(m.group(1), m.group(2))
            if owner and repo:
                gh.append((owner, repo))
    if gh:
        if len({(o, r) for o, r in gh}) > 1:
            flags.append("multi_repo")
        owner, repo = gh[0]
        return f"https://github.com/{owner}/{repo}", "github", flags

    for text in haystacks:
        m = OTHER_HOST_RE.search(text)
        if m:
            host = m.group(1).split(".")[0]
            return m.group(0).rstrip(_TRAILING), host, flags
    return None, None, flags


def classify_repo(gh_result: dict[str, Any] | None, host: str | None) -> dict[str, Any]:
    """Map a GitHub-check result (or a non-github host) to a repo classification.

    Pure: takes the raw check dict so it is testable without hitting the network.
    NEVER returns 'dead' for our own failures (rate-limit / network) — only for a
    confirmed 404 / private / empty repo.
    """
    if host is None:
        return {"status": REPO_NONE}
    if host != "github":
        return {"status": REPO_UNVERIFIABLE, "reason": f"host_{host}"}
    if not gh_result:
        return {"status": REPO_UNVERIFIABLE, "reason": "no_result"}
    st = gh_result.get("status")
    if st == "active":
        return {
            "status": REPO_ACTIVE,
            "stars": gh_result.get("stars"),
            "pushed_at": gh_result.get("pushed_at"),
        }
    if st == "dead":
        return {
            "status": REPO_DEAD,
            "reason": gh_result.get("reason"),
            "stars": gh_result.get("stars"),
            "pushed_at": gh_result.get("pushed_at"),
        }
    # unverifiable (ratelimit / network / unexpected http) → NEUTRAL
    return {"status": REPO_UNVERIFIABLE, "reason": gh_result.get("reason", "unknown")}


def rollup_tier(ann: QualityAnnotation, *, author_h_strong: int = 30, infl_strong: int = 5,
                repo_active_min_stars: int = 0) -> tuple[str, list[str]]:
    """Collapse signals into (tier, flags). Only repo_claimed_but_dead can drop
    below neutral; no_repo / unverifiable stay neutral."""
    flags = list(ann.quality_flags or [])
    strong = False
    if ann.author_h_max is not None and ann.author_h_max >= author_h_strong:
        strong = True
        flags.append("established_author")
    if (ann.influential_citation_count or 0) >= infl_strong:
        strong = True
        flags.append("influential")
    if ann.repo_status == REPO_ACTIVE and (ann.repo_stars or 0) >= repo_active_min_stars:
        strong = True
        flags.append("repo_active")

    if ann.repo_status == REPO_DEAD:
        # Penalize takes precedence: a dead claimed repo is a churn signal even
        # if the author is established. Mark weak but keep any positive flags
        # visible so the reranker sees the full picture.
        flags.append("repo_claimed_but_dead")
        return TIER_WEAK, flags
    if strong:
        return TIER_STRONG, flags
    return TIER_NEUTRAL, flags


# ── Network helpers ─────────────────────────────────────────────────────────

def _github_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def github_check(owner: str, repo: str, token: str | None, *, timeout: int | None = None) -> dict[str, Any]:
    """One GET to the repo metadata endpoint. Returns a dict with 'status' in
    {'active','dead','unverifiable'} plus stars/pushed_at when available.

    timeout defaults to the configured io.github_timeout when not overridden."""
    if timeout is None:
        timeout = GITHUB_TIMEOUT_S
        if timeout is None:
            raise RuntimeError(
                "quality_signal is unconfigured — call config.load_config() (which runs "
                "lib.runtime.apply) before checking GitHub repos."
            )
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "arxiv-recommender/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=timeout)
    except requests.RequestException:
        return {"status": "unverifiable", "reason": "network"}
    if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
        return {"status": "unverifiable", "reason": "ratelimit"}
    if r.status_code == 404:
        return {"status": "dead", "reason": "404"}
    if r.status_code in (403, 451):
        return {"status": "dead", "reason": "private_or_blocked"}
    if r.status_code != 200:
        return {"status": "unverifiable", "reason": f"http_{r.status_code}"}
    try:
        j = r.json()
    except ValueError:
        return {"status": "unverifiable", "reason": "bad_json"}
    if j.get("private") or j.get("size", 0) == 0 or not j.get("default_branch"):
        return {"status": "dead", "reason": "empty_or_private",
                "stars": j.get("stargazers_count"), "pushed_at": j.get("pushed_at")}
    return {"status": "active", "stars": j.get("stargazers_count"),
            "pushed_at": j.get("pushed_at")}


def _s2_quality_batch(arxiv_ids: list[str]) -> dict[str, dict[str, Any]]:
    """One S2 batch call. Returns {arxiv_id: {h_max, h_median, cite_max,
    citation_count, influential, venue, venue_type}}."""
    if not arxiv_ids:
        return {}
    prefixed = [f"ArXiv:{a}" for a in arxiv_ids]
    papers = s2_client.papers_batch(prefixed, fields=_S2_FIELDS)
    out: dict[str, dict[str, Any]] = {}
    for axid, paper in zip(arxiv_ids, papers):
        if not paper:
            continue
        authors = paper.get("authors") or []
        h = [a.get("hIndex") for a in authors if isinstance(a.get("hIndex"), int)]
        cites = [a.get("citationCount") for a in authors if isinstance(a.get("citationCount"), int)]
        pv = paper.get("publicationVenue") or {}
        out[axid] = {
            "h_max": max(h) if h else None,
            "h_median": (sorted(h)[len(h) // 2] if h else None),
            "cite_max": max(cites) if cites else None,
            "citation_count": paper.get("citationCount"),
            "influential": paper.get("influentialCitationCount"),
            "venue": paper.get("venue") or pv.get("name") or None,
            "venue_type": pv.get("type") or None,
        }
    return out


# ── Cache ───────────────────────────────────────────────────────────────────

def _cache_read(cache_dir: Path | None, axid: str, max_age_days: int | None) -> QualityAnnotation | None:
    if not cache_dir:
        return None
    p = cache_dir / f"{axid}.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if max_age_days is not None:
            fetched = data.get("_fetched_at_utc")
            if fetched:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched)).days
                if age > max_age_days:
                    return None
        data.pop("_fetched_at_utc", None)
        return QualityAnnotation(**data)
    except Exception as e:
        print(f"[quality] WARNING: corrupt cache for {axid} ({e}); recomputing", file=sys.stderr)
        return None


def _cache_write(cache_dir: Path | None, axid: str, ann: QualityAnnotation) -> None:
    if not cache_dir:
        return
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(ann)
        payload["_fetched_at_utc"] = datetime.now(timezone.utc).isoformat()
        (cache_dir / f"{axid}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[quality] WARNING: cache write failed for {axid} ({e}); annotation not persisted",
              file=sys.stderr)


# ── Orchestrator ─────────────────────────────────────────────────────────────

def annotate(
    candidates: list[dict[str, Any]],
    *,
    use_author_prior: bool = True,
    use_paper_influence: bool = True,
    use_repo_check: bool = True,
    author_h_strong: int = 30,
    infl_strong: int = 5,
    repo_active_min_stars: int = 0,
    cache_dir: Path | None = None,
    cache_max_age_days: int | None = 7,
) -> dict[str, QualityAnnotation]:
    """Annotate candidates with quality signals. NEVER raises on network failure
    — degrades to neutral. Returns {arxiv_id: QualityAnnotation}."""
    axids = [c.get("arxiv_id") for c in candidates if c.get("arxiv_id")]
    result: dict[str, QualityAnnotation] = {}

    # Cache lookup first.
    to_fetch: list[str] = []
    for axid in axids:
        cached = _cache_read(cache_dir, axid, cache_max_age_days)
        if cached is not None:
            result[axid] = cached
        else:
            to_fetch.append(axid)

    # S2 batch for the uncached set.
    s2: dict[str, dict[str, Any]] = {}
    if to_fetch and (use_author_prior or use_paper_influence):
        try:
            s2 = _s2_quality_batch(to_fetch)
        except Exception as e:  # noqa: BLE001 — degraded, but loud
            print(f"[quality] WARNING: S2 batch DROPPED — author prior/influence missing: {e}",
                  file=sys.stderr)

    token = _github_token() if use_repo_check else None
    by_axid = {c.get("arxiv_id"): c for c in candidates}
    github_exhausted = False

    for axid in to_fetch:
        ann = QualityAnnotation()
        meta = s2.get(axid) or {}
        if use_author_prior:
            ann.author_h_max = meta.get("h_max")
            ann.author_h_median = meta.get("h_median")
            ann.author_cite_max = meta.get("cite_max")
        if use_paper_influence:
            ann.paper_citation_count = meta.get("citation_count")
            ann.influential_citation_count = meta.get("influential")
            ann.venue = meta.get("venue")
            ann.venue_type = meta.get("venue_type")

        if use_repo_check:
            url, host, flags = extract_repo_url(by_axid.get(axid) or {})
            ann.repo_url, ann.repo_host = url, host
            ann.quality_flags = list(flags)
            gh_result = None
            if host == "github" and not github_exhausted:
                owner_repo = url.replace("https://github.com/", "").split("/")
                gh_result = github_check(owner_repo[0], owner_repo[1], token)
                if gh_result.get("reason") == "ratelimit":
                    github_exhausted = True  # stop hammering GitHub for the rest of this run
            cls = classify_repo(gh_result, host)
            ann.repo_status = cls["status"]
            ann.repo_stars = cls.get("stars")
            ann.repo_pushed_at = cls.get("pushed_at")

        tier, tier_flags = rollup_tier(
            ann, author_h_strong=author_h_strong, infl_strong=infl_strong,
            repo_active_min_stars=repo_active_min_stars,
        )
        ann.quality_tier = tier
        ann.quality_flags = tier_flags
        result[axid] = ann
        _cache_write(cache_dir, axid, ann)

    return result
