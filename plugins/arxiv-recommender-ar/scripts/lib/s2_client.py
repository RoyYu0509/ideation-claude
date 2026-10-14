"""Semantic Scholar Graph API client. Unkeyed: courtesy 1 req/sec.

We use the public REST endpoints documented at
https://api.semanticscholar.org/api-docs/graph.
"""
from __future__ import annotations

import os
import random
import time
from typing import Any, Iterable

try:
    import fcntl                      # POSIX only; the cross-process pacer degrades
except ImportError:                  # gracefully to per-process pacing without it
    fcntl = None

import requests

S2_BASE = "https://api.semanticscholar.org/graph/v1"

# Operational knobs — injected from config.yaml via lib.runtime.apply(cfg)
# (called automatically by config.load_config()). They start as None so that any
# use before the config is loaded raises loudly instead of using a hidden literal.
API_KEY: str | None = None            # researcher.s2_api_key (overrides env var when set)
MIN_INTERVAL_S: float | None = None   # unkeyed courtesy pace between requests
RETRIES: int | None = None            # attempts per request before giving up
SLEEP_429_S: float | None = None      # BASE of the exponential backoff on HTTP 429
BACKOFF_CAP_S: float | None = None    # ceiling for that backoff
TIMEOUT_S: int | None = None          # per-request timeout
LIMIT_PER_PAGE: int | None = None     # author_papers page size
MAX_PAPERS: int | None = None         # author_papers cap
CHUNK_SIZE: int | None = None         # papers_batch POST chunk size
REFS_CHUNK_SIZE: int | None = None    # papers_references chunk size — nested `references` are capped PER REQUEST
REFS_RETRY_CHUNK_SIZE = 20            # second pass for papers the first pass under-delivered (mechanism, not a knob)
TITLE_SEARCH_LIMIT: int | None = None  # search_by_title result cap
_last_call_ts = 0.0            # in-process fallback when fcntl is unavailable


def _pace_file() -> str:
    """Host-wide pace file. Override with ARXIV_REC_S2_PACE_FILE (e.g. to give
    a second concurrent run its own quota bucket).

    The default is a fixed per-user path, NOT tempfile.gettempdir(): that follows
    TMPDIR, so a caller that trims its env (TMPDIR unset -> /tmp) queued in a
    different file from one that kept it (/var/folders/.../T on macOS) and the two
    hit S2 concurrently, each pacing only itself (2026-09-25: two pace files found
    on one host during a 429 run)."""
    env = os.environ.get("ARXIV_REC_S2_PACE_FILE")
    if env:
        return env
    d = os.path.join(os.path.expanduser("~"), ".cache", "arxiv-recommender")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "s2.pace")


def _require_configured() -> None:
    if MIN_INTERVAL_S is None:
        raise RuntimeError(
            "s2_client is unconfigured — call config.load_config() (which runs "
            "lib.runtime.apply) before making Semantic Scholar requests."
        )


def _throttle() -> None:
    """Pace requests across EVERY process on this host, not just this one.

    Each subagent runs its own Python interpreter, so a module-level timestamp
    paces nothing: N concurrent agents hit S2 at N x the configured rate and the
    run 429s out (2026-W35: 26 of 38 prior-art queries came back empty, and the
    screen stage silently read that as "no related work"). Holding an exclusive
    flock across the sleep turns concurrent callers into one global queue at
    1/MIN_INTERVAL_S. The timestamp is wall-clock on purpose -- time.monotonic()
    has a per-process origin and is meaningless once shared through a file."""
    _require_configured()
    global _last_call_ts
    if fcntl is None:                                   # non-POSIX fallback
        wait = MIN_INTERVAL_S - (time.monotonic() - _last_call_ts)
        if wait > 0:
            time.sleep(wait)
        _last_call_ts = time.monotonic()
        return
    fd = os.open(_pace_file(), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)                  # queue: held across the sleep
        raw = os.read(fd, 64).decode("ascii", "ignore").strip()
        try:
            last = float(raw)
        except ValueError:
            last = 0.0
        wait = MIN_INTERVAL_S - (time.time() - last)
        if wait > 0:
            time.sleep(min(wait, MIN_INTERVAL_S))       # clamp: a future/corrupt stamp cannot wedge the queue
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, f"{time.time():.6f}".encode("ascii"))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _retryable(code: int) -> bool:
    """429 = "slow down" (S2's words). 5xx = the service faltered, and S2's own FAQ
    asks clients to ride those out with exponential backoff rather than failing.
    Measured 2026-09-02 on a 6-agent live run at 2s pacing: zero 429s and four
    HTTP 500s — the transient we actually hit is the one we were not retrying."""
    return code == 429 or code >= 500


def _backoff(resp, attempt: int) -> None:
    """Sleep after a 429. Semantic Scholar's own guidance is "you're sending too
    many requests, please slow down" + retry with exponential backoff; the keyed
    limit is 1 RPS on all endpoints.

    S2 returns NO Retry-After and no RateLimit headers (verified against the live
    API 2026-09-02), so we honour one if it ever appears and otherwise back off
    exponentially with FULL JITTER — a uniform draw from [0, base*2^attempt]. The
    jitter is the load-bearing part here: this client runs in many subagent
    processes at once, and a fixed sleep makes every throttled process retry in
    lockstep, which is what turns one throttle into a thundering herd."""
    ra = None
    try:
        ra = resp.headers.get("Retry-After") if resp is not None else None
    except Exception:
        ra = None
    if ra:
        try:
            time.sleep(min(float(ra), BACKOFF_CAP_S)); return
        except (TypeError, ValueError):
            pass
    ceiling = min(SLEEP_429_S * (2 ** attempt), BACKOFF_CAP_S)
    time.sleep(random.uniform(0.0, ceiling))


def _keys() -> list[str]:
    """Every configured key, in priority order, de-duplicated.

    S2 quotas are PER KEY, so a second key is a genuinely separate budget, not a
    spare copy — when one is throttled out the other still has its own 1 RPS. That
    makes key rotation a whole extra round of headroom, and a much cheaper fallback
    than dropping to web search, so it is tried first. Before 2026-09-02 this client
    read `API_KEY or SEMANTIC_SCHOLAR_API_KEY or S2_API_KEY` and stopped at the
    first non-empty one, so a second configured key was never used at all."""
    out, seen = [], set()
    for v in (API_KEY,
              os.environ.get("SEMANTIC_SCHOLAR_API_KEY"),
              os.environ.get("S2_API_KEY"),
              os.environ.get("S2_API_KEY_2")):
        if v and v not in seen:
            seen.add(v); out.append(v)
    return out


def _headers(key: str | None = None) -> dict[str, str]:
    h = {"Accept": "application/json", "User-Agent": "arxiv-recommender/0.1"}
    if key:
        h["x-api-key"] = key
    return h


def _send(do_request, label: str):
    """Run `do_request(headers)` across the KEY LADDER, each key with the full
    backoff retry ladder, and return the first non-retryable Response.

    Order of fallback, cheapest first: retry this key -> next key -> (caller's job)
    search the web. A 401/403 means the key itself was refused, so that key is
    abandoned immediately rather than burning its retries. Returns the last
    Response when everything is exhausted; the caller decides how to fail."""
    keys = _keys() or [None]
    last = None
    for ki, key in enumerate(keys):
        for attempt in range(RETRIES):
            _throttle()                                     # retries are requests too
            resp = do_request(_headers(key))
            if _retryable(resp.status_code):
                last = resp
                _backoff(resp, attempt)
                continue
            if resp.status_code in (401, 403):              # key refused — do not spend its retries
                last = resp
                break
            return resp
    return last


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{S2_BASE}{path}"
    resp = _send(lambda h: requests.get(url, params=params, headers=h, timeout=TIMEOUT_S), url)
    if resp is None or _retryable(resp.status_code) or resp.status_code in (401, 403):
        raise RuntimeError(f"S2 GET {url} exhausted {len(_keys()) or 1} key(s) x {RETRIES} retries "
                           f"(last status {resp.status_code if resp is not None else 'none'})")
    resp.raise_for_status()
    return resp.json()


def author_details(
    author_id: str,
    fields: Iterable[str] = ("name",),
) -> dict[str, Any]:
    """Fetch author metadata (name, etc.) from S2."""
    return _get(f"/author/{author_id}", {"fields": ",".join(fields)})


def author_papers(
    author_id: str,
    fields: Iterable[str] = (
        "paperId",
        "title",
        "abstract",
        "year",
        "venue",
        "externalIds",
        "fieldsOfStudy",
        "s2FieldsOfStudy",
        "references.paperId",
    ),
    limit_per_page: int | None = None,
    max_papers: int | None = None,
) -> list[dict[str, Any]]:
    """Page through an author's papers. Returns the raw S2 paper dicts.

    limit_per_page / max_papers default to the configured io.s2_* values when
    not explicitly overridden by the caller."""
    if limit_per_page is None:
        limit_per_page = LIMIT_PER_PAGE
    if max_papers is None:
        max_papers = MAX_PAPERS
    out: list[dict[str, Any]] = []
    offset = 0
    fields_str = ",".join(fields)
    while True:
        data = _get(
            f"/author/{author_id}/papers",
            {"fields": fields_str, "offset": offset, "limit": limit_per_page},
        )
        batch = data.get("data", []) or []
        if not batch:
            break
        out.extend(batch)
        if len(out) >= max_papers:
            return out[:max_papers]
        next_offset = data.get("next")
        if next_offset is None:
            break
        offset = next_offset
    return out


def _paper_by_key(key: str, fields: Iterable[str] = ("paperId", "references.paperId")) -> dict[str, Any] | None:
    try:
        return _get(f"/paper/{key}", {"fields": ",".join(fields)})
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise


def paper_by_arxiv(arxiv_id: str, fields: Iterable[str] = ("paperId", "references.paperId")) -> dict[str, Any] | None:
    """Look up an S2 paper by its arXiv ID (e.g., '2410.12345')."""
    return _paper_by_key(f"arXiv:{arxiv_id}", fields)


def papers_batch(
    paper_ids: list[str],
    fields: Iterable[str] = ("paperId", "references.paperId"),
    chunk_size: int | None = None,
) -> list[dict[str, Any] | None]:
    """Bulk-fetch papers by ID. Returns a list aligned with input (None = not found).

    paper_ids: S2 IDs or externally-prefixed IDs like 'ArXiv:2410.12345'.
    Sends ceil(len/chunk_size) POST requests instead of one per paper.
    chunk_size defaults to the configured io.s2_chunk_size when not overridden.
    """
    if not paper_ids:
        return []
    if chunk_size is None:
        chunk_size = CHUNK_SIZE
    fields_str = ",".join(fields)
    results: list[dict[str, Any] | None] = [None] * len(paper_ids)
    url = f"{S2_BASE}/paper/batch"
    for start in range(0, len(paper_ids), chunk_size):
        chunk = paper_ids[start : start + chunk_size]
        # S2 batch requires `fields` as a QUERY param; passing it in the JSON body is
        # silently ignored (you get only paperId+title back). This previously no-op'd
        # both citation_signal (no references) and the quality signal (no author
        # hIndex). Keep fields in params.
        resp = _send(lambda h: requests.post(url, params={"fields": fields_str},
                                             json={"ids": chunk}, headers=h, timeout=TIMEOUT_S),
                     "/paper/batch")
        if resp is None or _retryable(resp.status_code) or resp.status_code in (401, 403):
            raise RuntimeError(f"S2 POST /paper/batch exhausted {len(_keys()) or 1} key(s) x {RETRIES} "
                               f"retries (last status {resp.status_code if resp is not None else 'none'})")
        resp.raise_for_status()
        for i, paper in enumerate(resp.json()):
            results[start + i] = paper or None
    return results


def papers_references(
    paper_ids: list[str],
    extra_fields: Iterable[str] = (),
) -> tuple[list[set[str] | None], list[dict[str, Any] | None], dict[str, int]]:
    """Reference-id sets for many papers, aligned with the input (None = not on S2), plus the
    `extra_fields` of each paper and a stats dict.

    Why not plain papers_batch: the batch endpoint caps the NESTED `references` it returns per
    request. Measured 2026-09-12 on 500 papers with 29,154 references: chunks of 500 returned
    references for 117 papers, 300 → 217, 200 → 289, 100 → 332, 50 → 333 — the remaining ~33%
    have a referenceCount > 0 but no reference records on ANY endpoint (single paper,
    /references), i.e. an S2 data limit, not truncation. The cap shows up as an EMPTY nested
    list (never a partial one; referenceCount also counts references S2 could not link to a
    paper, so a list shorter than the count is normal). So: pass 1 in chunks of
    REFS_CHUNK_SIZE (≤ 100), then ONE retry in chunks of REFS_RETRY_CHUNK_SIZE for papers that
    came back with an empty list despite referenceCount > 0; what is still empty after that
    is reported in stats["unresolved"], never silently treated as "no references".
    """
    n = len(paper_ids)
    refs: list[set[str] | None] = [None] * n
    extras: list[dict[str, Any] | None] = [None] * n
    counts: list[int | None] = [None] * n
    raw: list[int] = [0] * n                 # nested entries returned, before dropping unlinked ones
    extra_fields = tuple(extra_fields)
    fields = ("paperId", "referenceCount", "references.paperId") + extra_fields

    def _take(i: int, paper: dict[str, Any] | None) -> None:
        if not paper:
            return
        entries = paper.get("references") or []
        raw[i] = len(entries)
        refs[i] = {r.get("paperId") for r in entries if r.get("paperId")}
        counts[i] = paper.get("referenceCount")
        extras[i] = {k: paper.get(k) for k in extra_fields}

    if not paper_ids:
        return refs, extras, {"n": 0, "found": 0, "with_refs": 0, "retried": 0, "recovered": 0, "unresolved": 0}
    for i, paper in enumerate(papers_batch(paper_ids, fields=fields, chunk_size=REFS_CHUNK_SIZE)):
        _take(i, paper)

    def _short(i: int) -> bool:
        return refs[i] is not None and (counts[i] or 0) > 0 and raw[i] == 0

    retry = [i for i in range(n) if _short(i)]
    if retry:
        got = papers_batch([paper_ids[i] for i in retry], fields=fields, chunk_size=REFS_RETRY_CHUNK_SIZE)
        for i, paper in zip(retry, got):
            if paper and paper.get("references"):
                _take(i, paper)
    recovered = sum(1 for i in retry if raw[i] > 0)
    stats = {"n": n, "found": sum(1 for r in refs if r is not None),
             "with_refs": sum(1 for r in refs if r), "retried": len(retry), "recovered": recovered,
             "unresolved": sum(1 for i in range(n) if _short(i))}
    return refs, extras, stats


def paper_by_id(
    paper_id: str,
    fields: Iterable[str] = ("paperId", "references.paperId"),
) -> dict[str, Any] | None:
    """Look up an S2 paper by its S2 paperId."""
    return _paper_by_key(paper_id, fields)


def search_by_title(
    title: str,
    fields: Iterable[str] = (
        "paperId",
        "title",
        "abstract",
        "year",
        "venue",
        "externalIds",
        "s2FieldsOfStudy",
        "references.paperId",
    ),
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Search S2 papers by title string. Returns raw S2 dicts.

    limit defaults to the configured io.s2_title_search_limit when not overridden."""
    if limit is None:
        limit = TITLE_SEARCH_LIMIT
    data = _get("/paper/search", {"query": title, "fields": ",".join(fields), "limit": limit})
    return data.get("data") or []


def recommendations_for_paper(
    paper_key: str,
    fields: Iterable[str] = (
        "paperId",
        "title",
        "abstract",
        "year",
        "venue",
        "externalIds",
    ),
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch S2's related-paper recommendations for one paper.

    paper_key: an S2 paperId or an externally-prefixed key like 'ArXiv:2410.12345'.
    Lives on the recommendations API (different base URL than the graph API),
    so it cannot go through _get; reuses the same throttle/headers/retry knobs.
    Returns [] when the paper is unknown to S2 (e.g. too new)."""
    url = f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_key}"
    params = {"fields": ",".join(fields), "limit": limit}
    resp = _send(lambda h: requests.get(url, params=params, headers=h, timeout=TIMEOUT_S), url)
    if resp is not None and resp.status_code == 404:
        return []                                       # unknown to S2 (e.g. too new)
    if resp is None or _retryable(resp.status_code) or resp.status_code in (401, 403):
        raise RuntimeError(f"S2 GET {url} exhausted {len(_keys()) or 1} key(s) x {RETRIES} retries "
                           f"(last status {resp.status_code if resp is not None else 'none'})")
    resp.raise_for_status()
    return resp.json().get("recommendedPapers") or []


def normalize_paper(p: dict[str, Any]) -> dict[str, Any]:
    """Convert an S2 paper dict to our compact internal shape."""
    ext = p.get("externalIds") or {}
    arxiv_id = ext.get("ArXiv")
    cats: list[str] = []
    for f in (p.get("s2FieldsOfStudy") or []):
        cat = f.get("category")
        if cat:
            cats.append(cat)
    refs = [r.get("paperId") for r in (p.get("references") or []) if r.get("paperId")]
    return {
        "paper_id": p.get("paperId"),
        "arxiv_id": arxiv_id,
        "title": p.get("title") or "",
        "abstract": p.get("abstract"),
        "year": p.get("year"),
        "venue": p.get("venue"),
        "categories": cats,
        "reference_ids": refs,
    }
