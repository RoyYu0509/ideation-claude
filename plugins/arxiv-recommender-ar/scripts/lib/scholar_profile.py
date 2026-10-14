"""Google Scholar profile reader — the preferred paper-list source (REC-SYSTEM-V2 A1, 2026-09-12).

ONE request per profile build, robots.txt-compliant: `/citations?user=` is allowed but
`cstart` paging is disallowed, so we read the single page sorted by date (the newest
<= io.scholar_pagesize works) and never page. The request says who it is (USER_AGENT);
a CAPTCHA / "unusual traffic" answer raises ScholarBlocked and is NOT retried, rotated
around or otherwise worked around — the caller asks the owner to save the page from a
browser and re-runs with --scholar-html.

Parsing keys on the profile table's classes:
  row      tr.gsc_a_tr
  title    a.gsc_a_at
  authors  1st div.gs_gray   (abbreviated, e.g. "Y Yu, CH Ho, Y Wang"; long lists end in "...")
  venue    2nd div.gs_gray   (arXiv preprints read "arXiv preprint arXiv:2608.19797"; some "arXiv: 2601.11942")
  year     td.gsc_a_y        (NOT any .gs_ibl — the citation-count cell carries that class too,
                              which once turned a 1268-citation count into a "year")
  cites    td.gsc_a_c a
  name     div#gsc_prf_in
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from lxml import html as lhtml

USER_AGENT = "arxiv-recommender/0.1 (research-profile builder; one request per build)"

_BLOCK_RE = re.compile(r"captcha|unusual traffic|not a robot", re.I)
_ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})", re.I)
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{12}$")


class ScholarBlocked(RuntimeError):
    """Scholar answered with a block/CAPTCHA page (or a non-200)."""


def user_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if _USER_ID_RE.match(s):
        return s
    uid = (parse_qs(urlparse(s).query).get("user") or [None])[0]
    if not uid:
        raise ValueError(f"not a Google Scholar profile URL (no user= parameter): {url_or_id!r}")
    return uid


def profile_url(url_or_id: str, base_url: str, pagesize: int) -> str:
    """The one URL we read. `user=` comes first because robots.txt allows the prefix
    '/citations?user='; there is deliberately no cstart parameter."""
    return f"{base_url}?" + urlencode([
        ("user", user_id(url_or_id)), ("hl", "en"),
        ("view_op", "list_works"), ("sortby", "pubdate"), ("pagesize", str(pagesize)),
    ])


def fetch_html(url: str, timeout: int) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
                     timeout=timeout)
    if r.status_code != 200:
        raise ScholarBlocked(f"Google Scholar answered HTTP {r.status_code} for {url}")
    if "gsc_a_tr" not in r.text and _BLOCK_RE.search(r.text):
        raise ScholarBlocked(f"Google Scholar answered with a CAPTCHA / block page for {url}")
    return r.text


def _cls(tag: str, cls: str) -> str:
    return f".//{tag}[contains(concat(' ', normalize-space(@class), ' '), ' {cls} ')]"


def _text(nodes: list) -> str:
    return " ".join(nodes[0].text_content().split()) if nodes else ""


def _int(s: str) -> int | None:
    s = s.strip()
    return int(s) if s.isdigit() else None


def parse(text: str) -> dict:
    """{'name': str | None, 'rows': [{title, authors_abbrev, venue, year, scholar_citations, arxiv_id}]}"""
    if "gsc_a_tr" not in text and _BLOCK_RE.search(text):
        raise ScholarBlocked("the page is a CAPTCHA / block page, not a Scholar profile")
    doc = lhtml.fromstring(text)
    name = _text(doc.xpath("//div[@id='gsc_prf_in']")) or None
    rows = []
    for tr in doc.xpath(_cls("tr", "gsc_a_tr")):
        title = _text(tr.xpath(_cls("a", "gsc_a_at")))
        if not title:
            continue
        grays = tr.xpath(_cls("div", "gs_gray"))
        venue = " ".join(grays[1].text_content().split()) if len(grays) > 1 else ""
        m = _ARXIV_RE.search(venue)
        rows.append({
            "title": title,
            "authors_abbrev": " ".join(grays[0].text_content().split()) if grays else "",
            "venue": venue,
            "year": _int(_text(tr.xpath(_cls("td", "gsc_a_y")))),
            "scholar_citations": _int(_text(tr.xpath(_cls("td", "gsc_a_c") + "//a"))),
            "arxiv_id": m.group(1) if m else None,
        })
    return {"name": name, "rows": rows}
