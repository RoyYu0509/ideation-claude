"""Offline tests for scripts/local_fetch_arxiv.py (the zero-dependency, runs-on-
laptop arXiv fetcher driven by build_shared_cache.py's off-box fetch path,
config io.arxiv_fetch_via_local).

No network: we feed a captured arXiv Atom page to parse_feed() and assert the
emitted candidate schema matches lib.arxiv_client.fetch_recent exactly, and that
build_query is byte-for-byte identical to arxiv_client._build_query.
"""
from datetime import datetime, timezone

import local_fetch_arxiv as lf
from lib import arxiv_client

# The exact key set fetch_recent emits per candidate (ARCHITECTURE.md contract).
EXPECTED_KEYS = {
    "arxiv_id", "title", "abstract", "authors", "submitted", "categories",
    "primary_category", "url", "comment", "links", "doi",
}

SAMPLE_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>2</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <entry>
    <id>http://arxiv.org/abs/2406.12345v2</id>
    <published>2026-06-03T10:00:00Z</published>
    <title>A Great Paper on Numerics</title>
    <summary>  We propose a method.  </summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <arxiv:comment>10 pages, code at github.com/foo/bar</arxiv:comment>
    <link href="http://arxiv.org/abs/2406.12345v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2406.12345v2" rel="related" type="application/pdf"/>
    <arxiv:primary_category term="math.NA" scheme="http://arxiv.org/schemas/atom"/>
    <category term="math.NA" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.NA" scheme="http://arxiv.org/schemas/atom"/>
    <arxiv:doi>10.1000/xyz123</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/cond-mat/0703123v1</id>
    <published>2026-06-02T08:00:00Z</published>
    <title>Old Style ID Paper</title>
    <summary>Another abstract.</summary>
    <author><name>Carol White</name></author>
    <link href="http://arxiv.org/abs/cond-mat/0703123v1" rel="alternate"/>
    <arxiv:primary_category term="cond-mat.mtrl-sci" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cond-mat.mtrl-sci"/>
  </entry>
</feed>
"""


def test_parse_feed_total_and_count():
    cands, total = lf.parse_feed(SAMPLE_FEED)
    assert total == 2
    assert len(cands) == 2


def test_candidate_schema_matches_fetch_recent():
    cands, _ = lf.parse_feed(SAMPLE_FEED)
    for c in cands:
        assert set(c.keys()) == EXPECTED_KEYS


def test_new_style_id_and_fields():
    cands, _ = lf.parse_feed(SAMPLE_FEED)
    c = cands[0]
    assert c["arxiv_id"] == "2406.12345"          # version stripped
    assert c["url"] == "http://arxiv.org/abs/2406.12345v2"
    assert c["title"] == "A Great Paper on Numerics"
    assert c["abstract"] == "We propose a method."  # whitespace stripped
    assert c["authors"] == ["Alice Smith", "Bob Jones"]
    assert c["categories"] == ["math.NA", "cs.NA"]
    assert c["primary_category"] == "math.NA"
    assert c["submitted"] == "2026-06-03T10:00:00+00:00"
    assert c["comment"].startswith("10 pages")
    assert c["doi"] == "10.1000/xyz123"
    assert "http://arxiv.org/pdf/2406.12345v2" in c["links"]


def test_old_style_id_and_missing_optionals():
    cands, _ = lf.parse_feed(SAMPLE_FEED)
    c = cands[1]
    assert c["arxiv_id"] == "cond-mat/0703123"     # old-style id preserved
    assert c["comment"] is None
    assert c["doi"] is None
    assert c["primary_category"] == "cond-mat.mtrl-sci"


def test_build_query_matches_arxiv_client():
    cats = ["cs.NE", "stat.ML", "math.NA"]
    start = datetime(2026, 5, 29, 8, 30, tzinfo=timezone.utc)
    end = datetime(2026, 6, 5, 8, 30, tzinfo=timezone.utc)
    assert lf.build_query(cats, start, end) == arxiv_client._build_query(cats, start, end)
