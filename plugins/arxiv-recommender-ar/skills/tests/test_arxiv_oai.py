"""Offline tests for lib/arxiv_oai.py (the VPS-native OAI-PMH ingest parser) and
oai_ingest's first-version window filter.

No network: feed captured OAI ListRecords XML to parse_records and assert the
candidate schema matches fetch_recent, the resumptionToken is parsed, deleted
records are skipped; drive harvest() through a fake _http_get to check that
`submitted` is the arXivRaw v1 date (never the arXiv format's <created>) and that
oai_ingest keeps only papers FIRST submitted in the half-open window; and
unit-test resolve_set's category→fine-set mapping.
"""
import urllib.parse
from datetime import date

import pytest

import oai_ingest
from lib import arxiv_oai

FETCH_RECENT_KEYS = {
    "arxiv_id", "title", "abstract", "authors", "submitted", "categories",
    "primary_category", "url", "comment", "links", "doi",
}

# Two records: a genuinely-new one (created 2026-06-04) and an old ID re-versioned in
# the datestamp window — the live service reports <created> as the NEWEST version's
# date, so it looks just as new; plus a deleted header; plus a resumptionToken to
# confirm paging is parsed.
SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record>
      <header><identifier>oai:arXiv.org:2606.01234</identifier><datestamp>2026-06-04</datestamp>
        <setSpec>stat:stat:ML</setSpec></header>
      <metadata>
        <arXiv xmlns="http://arxiv.org/OAI/arXiv/">
          <id>2606.01234</id><created>2026-06-04</created><updated>2026-06-04</updated>
          <authors><author><keyname>Smith</keyname><forenames>Alice</forenames></author>
                   <author><keyname>Jones</keyname><forenames>Bob</forenames></author></authors>
          <title>A New Method for
            Learning</title>
          <categories>stat.ML cs.LG</categories>
          <comments>10 pages, code at github.com/foo/bar</comments>
          <doi>10.1000/xyz123</doi>
          <abstract>We propose a method.</abstract>
        </arXiv>
      </metadata>
    </record>
    <record>
      <header><identifier>oai:arXiv.org:1304.7018</identifier><datestamp>2026-06-04</datestamp></header>
      <metadata>
        <arXiv xmlns="http://arxiv.org/OAI/arXiv/">
          <id>1304.7018</id><created>2026-06-03</created><updated>2026-06-04</updated>
          <authors><author><keyname>Kreeft</keyname><forenames>Jasper</forenames></author></authors>
          <title>Old Paper</title><categories>cs.NA math.NA</categories>
          <abstract>An older paper, re-versioned.</abstract>
        </arXiv>
      </metadata>
    </record>
    <record><header status="deleted"><identifier>oai:arXiv.org:2606.00000</identifier></header></record>
    <resumptionToken cursor="0" completeListSize="2">TOKEN-PAGE-2</resumptionToken>
  </ListRecords>
</OAI-PMH>
"""


def test_parse_records_fields_and_token():
    recs, token = arxiv_oai.parse_records(SAMPLE)
    assert token == "TOKEN-PAGE-2"          # resumptionToken parsed
    assert len(recs) == 2                    # deleted record skipped
    c = recs[0]
    assert FETCH_RECENT_KEYS <= set(c.keys())
    assert c["arxiv_id"] == "2606.01234"
    assert c["title"] == "A New Method for Learning"   # whitespace collapsed
    assert c["abstract"] == "We propose a method."
    assert c["authors"] == ["Alice Smith", "Bob Jones"]  # forenames + keyname
    assert c["categories"] == ["stat.ML", "cs.LG"]
    assert c["primary_category"] == "stat.ML"
    assert c["submitted"] is None           # <created> is not the submission date; harvest() fills v1
    assert c["created"] == "2026-06-04"
    assert c["comment"].startswith("10 pages")
    assert c["doi"] == "10.1000/xyz123"
    assert c["url"] == "https://arxiv.org/abs/2606.01234"
    old = recs[1]
    assert old["arxiv_id"] == "1304.7018" and old["created"] == "2026-06-03"  # raw passthrough
    assert old["comment"] is None and old["doi"] is None


def test_no_records_match_returns_empty():
    xml = (b'<?xml version="1.0"?><OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
           b'<error code="noRecordsMatch">no matches</error></OAI-PMH>')
    recs, token = arxiv_oai.parse_records(xml)
    assert recs == [] and token is None


# First-version window. Modeled on the real record 2407.05788 as served on 2026-09-11:
# the arXiv format reports created=2026-08-19 (its v2), while arXivRaw lists
# v1 = 2024-07-08. Window under test: [2026-08-19, 2026-08-26).
WINDOW = (date(2026, 8, 19), date(2026, 8, 26))


def _arxiv_rec(aid, created, updated):
    return (f'<record><header><identifier>oai:arXiv.org:{aid}</identifier>'
            f'<datestamp>{updated}</datestamp></header><metadata>'
            f'<arXiv xmlns="http://arxiv.org/OAI/arXiv/"><id>{aid}</id><created>{created}</created>'
            f'<updated>{updated}</updated><authors><author><keyname>Doe</keyname>'
            f'<forenames>Jane</forenames></author></authors><title>Paper {aid}</title>'
            f'<categories>cs.LG</categories><abstract>Abstract.</abstract></arXiv></metadata></record>')


def _raw_rec(aid, *version_dates):
    versions = "".join(f'<version version="v{i}"><date>{d}</date><size>1kb</size></version>'
                       for i, d in enumerate(version_dates, 1))
    return (f'<record><header><identifier>oai:arXiv.org:{aid}</identifier>'
            f'<datestamp>2026-08-26</datestamp></header><metadata>'
            f'<arXivRaw xmlns="http://arxiv.org/OAI/arXivRaw/"><id>{aid}</id>{versions}'
            f'<title>Paper {aid}</title><authors>Jane Doe</authors><categories>cs.LG</categories>'
            f'</arXivRaw></metadata></record>')


def _list_page(records, token=None):
    tok = f"<resumptionToken>{token}</resumptionToken>" if token else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
            f'<ListRecords>{"".join(records)}{tok}</ListRecords></OAI-PMH>').encode()


ARXIV_PAGE = _list_page([
    _arxiv_rec("2407.05788", "2026-08-19", "2026-08-20"),  # old ID, recent created → drop (v1 2024)
    _arxiv_rec("2608.14001", "2026-08-20", "2026-08-21"),  # new → keep
    _arxiv_rec("2608.13500", "2026-08-24", "2026-08-25"),  # v1 on the start day, v2 later → keep
    _arxiv_rec("2608.12000", "2026-08-21", "2026-08-22"),  # same yymm, v1 1s before start → drop
    _arxiv_rec("2608.16000", "2026-08-26", "2026-08-26"),  # v1 on the (exclusive) end day → drop
    _arxiv_rec("2608.15000", "2026-08-22", "2026-08-23"),  # absent from the arXivRaw pass → drop
])
RAW_PAGES = {
    "arXivRaw": _list_page([
        _raw_rec("2407.05788", "Mon, 08 Jul 2024 09:49:38 GMT", "Wed, 19 Aug 2026 07:50:07 GMT"),
        _raw_rec("2608.14001", "Thu, 20 Aug 2026 12:00:00 GMT"),
        _raw_rec("2608.13500", "Wed, 19 Aug 2026 00:00:05 GMT", "Mon, 24 Aug 2026 09:00:00 GMT"),
    ], token="RAW-PAGE-2"),
    "RAW-PAGE-2": _list_page([
        _raw_rec("2608.12000", "Tue, 18 Aug 2026 23:59:59 GMT", "Fri, 21 Aug 2026 10:00:00 GMT"),
        _raw_rec("2608.16000", "Wed, 26 Aug 2026 00:00:01 GMT"),
    ]),
}


@pytest.fixture
def fake_oai(monkeypatch):
    """Serve harvest()'s requests from canned pages: by resumptionToken when present,
    else by metadataPrefix. Returns the (mutable) page map."""
    pages = {"arXiv": ARXIV_PAGE, **RAW_PAGES}

    def get(url):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        return pages[q.get("resumptionToken", q.get("metadataPrefix"))[0]]

    for name, val in (("BASE_URL", "https://oai.test/oai"), ("TIMEOUT_S", 1),
                      ("PAGE_DELAY_S", 0), ("MAX_PAGES", 5), ("_http_get", get)):
        monkeypatch.setattr(arxiv_oai, name, val)
    return pages


def test_harvest_submitted_is_first_version_not_created(fake_oai):
    recs = {r["arxiv_id"]: r for r in arxiv_oai.harvest("cs:cs:LG", "2026-08-19", "2026-08-26")}
    old = recs["2407.05788"]
    assert old["created"] == "2026-08-19"                     # what the arXiv format claims
    assert old["submitted"] == "2024-07-08T09:49:38+00:00"    # the real v1, from arXivRaw
    assert recs["2608.13500"]["submitted"] == "2026-08-19T00:00:05+00:00"  # v1, not v2
    assert recs["2608.12000"]["submitted"] == "2026-08-18T23:59:59+00:00"  # from raw page 2
    assert recs["2608.15000"]["submitted"] is None            # absent from the arXivRaw pass


def test_ingest_keeps_only_papers_first_submitted_in_window(fake_oai):
    recs = arxiv_oai.harvest("cs:cs:LG", "2026-08-19", "2026-08-26")
    kept = [r["arxiv_id"] for r in recs if oai_ingest._submitted_in_window(r, *WINDOW)]
    assert kept == ["2608.14001", "2608.13500"]


def test_consecutive_windows_share_no_day():
    next_week = (date(2026, 8, 26), date(2026, 9, 2))
    for ts in ("2026-08-25T23:59:59+00:00", "2026-08-26T00:00:00+00:00"):
        hits = [oai_ingest._submitted_in_window({"submitted": ts}, *w) for w in (WINDOW, next_week)]
        assert hits.count(True) == 1, ts


def test_harvest_fails_loud_when_arxivraw_pass_is_empty(fake_oai):
    fake_oai["arXivRaw"] = (b'<?xml version="1.0"?><OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
                            b'<error code="noRecordsMatch">no matches</error></OAI-PMH>')
    with pytest.raises(RuntimeError, match="arXivRaw"):
        arxiv_oai.harvest("cs:cs:LG", "2026-08-19", "2026-08-26")


SETSPECS = [
    "cs", "cs:cs:CE", "cs:cs:NA", "cs:cs:NE", "math:math:NA", "stat:stat:ML",
    "physics", "physics:cond-mat:mes-hall", "physics:cond-mat:mtrl-sci",
    "physics:physics:comp-ph",
]


def test_resolve_set_fine_mapping():
    assert arxiv_oai.resolve_set("cs.CE", SETSPECS) == "cs:cs:CE"
    assert arxiv_oai.resolve_set("math.NA", SETSPECS) == "math:math:NA"
    assert arxiv_oai.resolve_set("stat.ML", SETSPECS) == "stat:stat:ML"
    assert arxiv_oai.resolve_set("cond-mat.mes-hall", SETSPECS) == "physics:cond-mat:mes-hall"
    assert arxiv_oai.resolve_set("physics.comp-ph", SETSPECS) == "physics:physics:comp-ph"


def test_resolve_set_raises_on_unknown():
    with pytest.raises(ValueError):
        arxiv_oai.resolve_set("cs.ZZ", SETSPECS)
