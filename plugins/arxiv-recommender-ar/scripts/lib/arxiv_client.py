"""arXiv API client with built-in rate limiting via the `arxiv` package."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import arxiv

# Operational knobs — injected from config.yaml `io.arxiv_*` via lib.runtime.apply
# (called by config.load_config()). None until applied so unconfigured use raises.
PAGE_SIZE: int | None = None
DELAY_SECONDS: int | None = None
NUM_RETRIES: int | None = None

# Title-phrase queries use at most this many words: a whole title often carries LaTeX or
# punctuation that arXiv tokenizes differently, and a long phrase then matches nothing.
# A query-construction detail, not a tuning knob.
_TITLE_PHRASE_WORDS = 8
_LEAD_STOP = {"a", "an", "the", "on", "of", "for", "and", "to", "in", "with", "via", "toward", "towards"}


_CLIENT: arxiv.Client | None = None


def _client() -> arxiv.Client:
    """ONE client per process. arxiv.Client spaces its OWN consecutive requests by
    delay_seconds; a fresh client per call fired the profile build's ~25 title searches
    back-to-back and drew HTTP 429 (2026-09-12)."""
    global _CLIENT
    if PAGE_SIZE is None:
        raise RuntimeError(
            "arxiv_client is unconfigured — call config.load_config() (which runs "
            "lib.runtime.apply) before fetching from arXiv."
        )
    if _CLIENT is None:
        _CLIENT = arxiv.Client(page_size=PAGE_SIZE, delay_seconds=DELAY_SECONDS, num_retries=NUM_RETRIES)
    return _CLIENT


def _record(r: Any) -> dict[str, Any]:
    """One arXiv result → our candidate dict. `submitted` is the FIRST version's date
    (the API's <published>); `updated` is the latest version's."""
    return {
        "arxiv_id": re.sub(r"v\d+$", "", r.get_short_id()),
        "title": " ".join((r.title or "").split()),
        "abstract": (r.summary or "").strip(),
        "authors": [a.name for a in r.authors],
        "submitted": r.published.astimezone(timezone.utc).isoformat() if r.published else None,
        "updated": r.updated.astimezone(timezone.utc).isoformat() if getattr(r, "updated", None) else None,
        "categories": list(r.categories),
        "primary_category": r.primary_category,
        "url": r.entry_id,
        # Kept for the quality signal's repo-URL extraction (authors often
        # put "code at github.com/..." in the comment, not the abstract).
        "comment": (r.comment or None),
        "links": [l.href for l in (r.links or []) if getattr(l, "href", None)],
        "doi": (r.doi or None),
    }


def _build_query(categories: Iterable[str], start_utc: datetime, end_utc: datetime) -> str:
    cat_q = " OR ".join(f"cat:{c}" for c in categories)
    if not cat_q:
        raise ValueError("at least one category required")
    fmt = "%Y%m%d%H%M"
    return (
        f"({cat_q}) AND submittedDate:[{start_utc.strftime(fmt)} TO {end_utc.strftime(fmt)}]"
    )


def fetch_recent(
    categories: list[str],
    window_days: int,
    max_results: int = 5000,
    end_utc: datetime | None = None,
) -> list[dict[str, Any]]:
    if end_utc is None:
        end_utc = datetime.now(timezone.utc)
    start_utc = end_utc - timedelta(days=window_days)
    q = _build_query(categories, start_utc, end_utc)
    search = arxiv.Search(
        query=q,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    out = []
    for r in _client().results(search):
        rec = _record(r)
        rec.pop("updated", None)          # fetch_recent's contract predates the field
        out.append(rec)
    return out


# ── Profile building (REC-SYSTEM-V2 A1) ──────────────────────────────────────

def fetch_by_ids(ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Full records for arXiv ids, keyed by id (version suffix stripped). Ids arXiv does
    not know are simply absent from the result."""
    uniq = list(dict.fromkeys(re.sub(r"v\d+$", "", i.strip()) for i in ids if i and i.strip()))
    out: dict[str, dict[str, Any]] = {}
    if not uniq:
        return out
    client = _client()
    for start in range(0, len(uniq), PAGE_SIZE):
        chunk = uniq[start:start + PAGE_SIZE]
        for r in client.results(arxiv.Search(id_list=chunk, max_results=len(chunk))):
            rec = _record(r)
            out[rec["arxiv_id"]] = rec
    return out


def title_phrase(title: str) -> str:
    """The quoted-phrase part of a title query: punctuation dropped, leading stop words
    skipped, at most _TITLE_PHRASE_WORDS words. (An UNquoted `ti:w1 AND ti:w2 …` query
    returned nothing even for a known title in the 2026-09-12 check; the quoted phrase hit.)"""
    words = re.sub(r"[^A-Za-z0-9]+", " ", title or "").split()
    while words and words[0].lower() in _LEAD_STOP:
        words.pop(0)
    return " ".join(words[:_TITLE_PHRASE_WORDS])


# British ↔ American spelling. A journal often prints "generalization" where the arXiv preprint
# (e.g. a UK co-author's) says "generalisation", and a quoted phrase then matches nothing
# (2026-09-12: the default researcher's "A theoretical case study of the generalization of …").
# A wrong variant only costs one empty query — the original phrase is always tried first.
_TO_BRITISH = [(r"(?<=[a-z]{3})ization", "isation"), (r"(?<=[a-z]{3})iz(e|es|ed|ing)\b", r"is\1"),
               (r"yz(e|ed|ing)\b", r"ys\1")]
_TO_AMERICAN = [(r"(?<=[a-z]{3})isation", "ization"), (r"yse\b", "yze")]


def _respell(s: str, rules) -> str:
    for pat, rep in rules:
        s = re.sub(pat, rep, s, flags=re.I)
    return s


def title_phrases(title: str) -> list[str]:
    """title_phrase() plus its British / American respellings, deduplicated, original first."""
    base = title_phrase(title)
    if not base:
        return []
    return list(dict.fromkeys([base, _respell(base, _TO_BRITISH), _respell(base, _TO_AMERICAN)]))


def search_title(title: str, max_results: int = 3) -> list[dict[str, Any]]:
    """Hits for every spelling of the title phrase (deduplicated); the caller picks the best match."""
    out: dict[str, dict[str, Any]] = {}
    for phrase in title_phrases(title):
        for r in _client().results(arxiv.Search(query=f'ti:"{phrase}"', max_results=max_results)):
            rec = _record(r)
            out.setdefault(rec["arxiv_id"], rec)
    return list(out.values())


def search_author(name: str, max_results: int) -> list[dict[str, Any]]:
    """`au:"Full Name"` — the fallback paper-list source when no Scholar profile is given.
    Callers must still confirm identity: a name query returns every namesake."""
    search = arxiv.Search(
        query=f'au:"{name}"',
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    return [_record(r) for r in _client().results(search)]
