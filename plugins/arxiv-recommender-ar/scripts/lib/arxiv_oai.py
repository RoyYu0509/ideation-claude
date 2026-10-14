"""arXiv OAI-PMH client — the VPS-native fixed-window ingest path.

arXiv's edge hard-blocks `export.arxiv.org/api/query` for datacenter IPs, but the
OAI-PMH endpoint (`export.arxiv.org/oai2`) returns 200 from the same IPs and
supports an arbitrary `from`/`until` date window — so it gives a STATELESS
"last N days" fetch (unlike the RSS feeds, which only expose one announcement
day). Records carry full metadata: abstract, authors, categories, plus
`comments`/`doi`.

The FIRST-version submission date — what "new in the window" means (the old API's
`submittedDate` semantics) — is NOT in the `arXiv` format: its `<created>` is the
LATEST version's date (verified 2026-09-11 on oaipmh.arxiv.org: 2407.05788 reports
created=2026-08-19, but its arXivRaw versions are v1 2024-07-08, v2 2026-08-19).
harvest() therefore makes a second pass over the `arXivRaw` format, which lists
every version's timestamp, and sets each record's `submitted` to its v1 timestamp.

We harvest by FINE-GRAINED set (e.g. `cs:cs:CE`, `physics:cond-mat:mes-hall`) so the
volume stays small (~tens of MB for a 7-day window across the user's categories),
instead of harvesting whole top-level archives. harvest() emits the same
per-candidate schema as lib.arxiv_client.fetch_recent.

Operational knobs are injected from config via lib.runtime.apply (None until
applied so an unconfigured call raises loudly).
"""
from __future__ import annotations

import ssl
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

# Injected from config.yaml via lib.runtime.apply.
BASE_URL: str | None = None
TIMEOUT_S: int | None = None
PAGE_DELAY_S: float | None = None
MAX_FLOW_CONTROL_WAIT_S: int | None = None
MAX_PAGES: int | None = None
USER_AGENT = "arxiv-recommender/0.2 (https://github.com/; mailto:" + os.environ.get("AR_CONTACT_EMAIL", "set-AR_CONTACT_EMAIL@example.com") + ")"

_OAI = "http://www.openarchives.org/OAI/2.0/"
_ARX = "http://arxiv.org/OAI/arXiv/"
_ARXR = "http://arxiv.org/OAI/arXivRaw/"


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _require_configured() -> None:
    if BASE_URL is None or TIMEOUT_S is None:
        raise RuntimeError(
            "arxiv_oai is unconfigured — call config.load_config() (which runs "
            "lib.runtime.apply) before harvesting."
        )


TRANSIENT_RETRIES = 4          # attempts for a dropped connection (separate budget from flow control)
TRANSIENT_BACKOFF_S = (3, 10, 30, 60)


def _http_get(url: str) -> bytes:
    """GET with OAI flow-control handling: a 503 carries a Retry-After telling us
    how long to wait before retrying the SAME request. Cap cumulative waiting.

    ALSO retries transient TRANSPORT failures (2026-09-03). A harvest walks hundreds of pages over tens of
    minutes, and arXiv's endpoint intermittently drops the TLS connection mid-stream
    (`URLError: [SSL: UNEXPECTED_EOF_WHILE_READING]`). Only HTTP 503 was retried before, so ONE such drop
    anywhere in the walk aborted the whole harvest and the caller returned a hard failure — observed on the
    first real backfill attempt, after cs.AI had already yielded 1608 in-window papers. That is fatal for an
    unattended multi-week run, where nobody is watching to restart it. Flow control and transport errors keep
    SEPARATE budgets on purpose: a 503 means "you are going too fast" (obey Retry-After), a dropped socket
    means "try again" (exponential backoff)."""
    _require_configured()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    waited = 0
    transient = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 503:
                raise
            retry_after = e.headers.get("Retry-After")
            try:
                delay = int(retry_after)
            except (TypeError, ValueError):
                delay = 10
            if waited + delay > MAX_FLOW_CONTROL_WAIT_S:
                raise RuntimeError(
                    f"OAI flow-control wait exceeded cap "
                    f"({waited}+{delay}s > {MAX_FLOW_CONTROL_WAIT_S}s) for {url}"
                ) from e
            time.sleep(delay)
            waited += delay
        except (urllib.error.URLError, ssl.SSLError, TimeoutError, ConnectionError) as e:
            if transient >= TRANSIENT_RETRIES:
                raise RuntimeError(
                    f"OAI transport failed {transient + 1}x for {url}: {type(e).__name__}: {e}"
                ) from e
            delay = TRANSIENT_BACKOFF_S[min(transient, len(TRANSIENT_BACKOFF_S) - 1)]
            print(f"[arxiv_oai] transient {type(e).__name__} ({e}); retry "
                  f"{transient + 1}/{TRANSIENT_RETRIES} in {delay}s", file=sys.stderr)
            time.sleep(delay)
            transient += 1


def _author_name(author: ET.Element) -> str:
    parts = [
        (author.findtext(_q(_ARX, "forenames")) or "").strip(),
        (author.findtext(_q(_ARX, "keyname")) or "").strip(),
        (author.findtext(_q(_ARX, "suffix")) or "").strip(),
    ]
    return " ".join(p for p in parts if p)


def _page(xml_bytes: bytes, ns: str, tag: str) -> tuple[list[ET.Element], str | None]:
    """Split one OAI ListRecords page into (each live record's <metadata>/<ns:tag>
    element, resumption_token). `resumption_token` is None on the last page. OAI
    `noRecordsMatch` returns ([], None); any other OAI <error> raises; deleted
    records are skipped."""
    root = ET.fromstring(xml_bytes)
    err = root.find(_q(_OAI, "error"))
    if err is not None:
        if err.get("code") == "noRecordsMatch":
            return [], None
        raise RuntimeError(f"OAI error {err.get('code')}: {(err.text or '').strip()}")

    out: list[ET.Element] = []
    for rec in root.iter(_q(_OAI, "record")):
        header = rec.find(_q(_OAI, "header"))
        if header is not None and header.get("status") == "deleted":
            continue
        md = rec.find(f"{_q(_OAI, 'metadata')}/{_q(ns, tag)}")
        if md is not None:
            out.append(md)

    tok_node = root.find(f".//{_q(_OAI, 'resumptionToken')}")
    token = tok_node.text.strip() if tok_node is not None and tok_node.text and tok_node.text.strip() else None
    return out, token


def parse_records(xml_bytes: bytes) -> tuple[list[dict[str, Any]], str | None]:
    """Parse one `arXiv`-format ListRecords page into (candidates, resumption_token).

    `created`/`updated` are passed through raw. `submitted` is left None: this
    format's `<created>` is the latest version's date, not the first submission,
    so harvest() fills `submitted` from the arXivRaw pass.
    """
    arxs, token = _page(xml_bytes, _ARX, "arXiv")
    out: list[dict[str, Any]] = []
    for arx in arxs:
        arxiv_id = (arx.findtext(_q(_ARX, "id")) or "").strip()
        created = (arx.findtext(_q(_ARX, "created")) or "").strip() or None
        updated = (arx.findtext(_q(_ARX, "updated")) or "").strip() or None
        cats_raw = (arx.findtext(_q(_ARX, "categories")) or "").strip()
        categories = cats_raw.split() if cats_raw else []
        authors_node = arx.find(_q(_ARX, "authors"))
        authors = (
            [_author_name(a) for a in authors_node.findall(_q(_ARX, "author"))]
            if authors_node is not None
            else []
        )
        out.append(
            {
                "arxiv_id": arxiv_id,
                "title": " ".join((arx.findtext(_q(_ARX, "title")) or "").split()),
                "abstract": (arx.findtext(_q(_ARX, "abstract")) or "").strip(),
                "authors": [a for a in authors if a],
                "submitted": None,  # filled by harvest() from the arXivRaw pass
                "categories": categories,
                "primary_category": categories[0] if categories else None,
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "comment": (arx.findtext(_q(_ARX, "comments")) or "").strip() or None,
                "links": [f"https://arxiv.org/abs/{arxiv_id}"],
                "doi": (arx.findtext(_q(_ARX, "doi")) or "").strip() or None,
                "created": created,
                "updated": updated,
            }
        )
    return out, token


def _raw_version_date(text: str | None) -> datetime | None:
    """arXivRaw `<version><date>` (RFC 2822, e.g. 'Mon, 08 Jul 2024 09:49:38 GMT') → aware UTC."""
    try:
        d = parsedate_to_datetime((text or "").strip())
    except (TypeError, ValueError):
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)


def parse_raw_records(xml_bytes: bytes) -> tuple[list[tuple[str, str]], str | None]:
    """Parse one `arXivRaw`-format ListRecords page into
    ([(arxiv_id, first-version ISO-8601 UTC timestamp)], resumption_token). The first
    version is the earliest `<version><date>`; a record with none parseable is omitted."""
    raws, token = _page(xml_bytes, _ARXR, "arXivRaw")
    out: list[tuple[str, str]] = []
    for raw in raws:
        arxiv_id = (raw.findtext(_q(_ARXR, "id")) or "").strip()
        dates = [d for v in raw.findall(_q(_ARXR, "version"))
                 if (d := _raw_version_date(v.findtext(_q(_ARXR, "date")))) is not None]
        if arxiv_id and dates:
            out.append((arxiv_id, min(dates).isoformat()))
    return out, token


def list_sets() -> list[str]:
    """Return every OAI setSpec (paginating through resumptionToken)."""
    _require_configured()
    specs: list[str] = []
    url = f"{BASE_URL}?verb=ListSets"
    pages = 0
    while url and pages < MAX_PAGES:
        root = ET.fromstring(_http_get(url))
        for s in root.iter(_q(_OAI, "setSpec")):
            if s.text:
                specs.append(s.text.strip())
        tok_node = root.find(f".//{_q(_OAI, 'resumptionToken')}")
        token = tok_node.text.strip() if tok_node is not None and tok_node.text and tok_node.text.strip() else None
        pages += 1
        if token:
            url = f"{BASE_URL}?verb=ListSets&resumptionToken={urllib.parse.quote(token)}"
            time.sleep(PAGE_DELAY_S)
        else:
            url = None
    return specs


def resolve_set(category: str, setspecs: list[str]) -> str:
    """Map a fine arXiv category (e.g. 'cond-mat.mes-hall') to its OAI setSpec
    (e.g. 'physics:cond-mat:mes-hall') by matching the setSpec ending in
    ':<archive>:<subcat>'. Top-level archives with no subcat (e.g. 'quant-ph')
    match ':<archive>' directly. Raises if none matches (no silent drop)."""
    archive, _, sub = category.partition(".")
    # top-level archive (e.g. quant-ph): match ":quant-ph" exactly at end
    suffix = (f":{archive}:{sub}" if sub else f":{archive}").lower()
    for s in setspecs:
        if s.lower().endswith(suffix):
            return s
    raise ValueError(
        f"no OAI set found for category '{category}' (looked for a setSpec ending "
        f"in '{suffix}'). Check the category is valid."
    )


def _list_records(setspec: str, from_date: str, until_date: str, prefix: str,
                  parse: Callable[[bytes], tuple[list, str | None]]) -> list:
    """Walk one set's ListRecords in metadata format `prefix` for the datestamp window
    [from_date, until_date] (YYYY-MM-DD, inclusive), following resumptionToken pages;
    `parse` turns one page into (items, token)."""
    _require_configured()
    params = urllib.parse.urlencode({
        "verb": "ListRecords", "metadataPrefix": prefix,
        "from": from_date, "until": until_date, "set": setspec,
    })
    url: str | None = f"{BASE_URL}?{params}"
    records: list = []
    pages = 0
    while url and pages < MAX_PAGES:
        recs, token = parse(_http_get(url))
        records.extend(recs)
        pages += 1
        if token:
            url = f"{BASE_URL}?verb=ListRecords&resumptionToken={urllib.parse.quote(token)}"
            time.sleep(PAGE_DELAY_S)
        else:
            url = None
    if pages >= MAX_PAGES and url:
        raise RuntimeError(
            f"set '{setspec}' ({prefix}) hit MAX_PAGES={MAX_PAGES} with more pages remaining — "
            f"raise io.oai_max_pages or narrow the window."
        )
    return records


def harvest(setspec: str, from_date: str, until_date: str) -> list[dict[str, Any]]:
    """Harvest one set's ListRecords for the datestamp window [from_date, until_date]
    (YYYY-MM-DD). Returns ALL records in the window, re-versioned old papers included,
    each with `submitted` = its FIRST-version timestamp from a second pass over the
    same window in the arXivRaw format (None if the record is missing from that pass,
    e.g. it changed between the two passes). The caller filters on `submitted`."""
    records = _list_records(setspec, from_date, until_date, "arXiv", parse_records)
    first = dict(_list_records(setspec, from_date, until_date, "arXivRaw", parse_raw_records))
    if records and not first:
        raise RuntimeError(
            f"set '{setspec}': arXivRaw pass returned no version dates for {len(records)} "
            f"records — cannot tell new papers from re-versioned ones (format change?)."
        )
    for r in records:
        r["submitted"] = first.get(r["arxiv_id"])
    return records
