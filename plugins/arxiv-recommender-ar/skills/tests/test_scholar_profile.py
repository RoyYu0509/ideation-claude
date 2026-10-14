"""Google Scholar profile reader (REC-SYSTEM-V2 A1). Synthetic fixture — no network, no real profile."""
import pytest

from lib import scholar_profile as S

FIXTURE = """<html><body><div id="gsc_prf_in">Ada Lovelace</div><table><tbody id="gsc_a_b">
<tr class="gsc_a_tr"><td class="gsc_a_t"><a href="#" class="gsc_a_at">Analytical engines for PDEs</a>
  <div class="gs_gray">A Lovelace, C Babbage</div>
  <div class="gs_gray">arXiv preprint arXiv:2601.00001<span class="gs_oph">, 2026</span></div></td>
  <td class="gsc_a_c"><a href="#" class="gsc_a_ac gs_ibl">12</a></td>
  <td class="gsc_a_y"><span class="gsc_a_h gsc_a_hc gs_ibl">2026</span></td></tr>
<tr class="gsc_a_tr"><td class="gsc_a_t"><a href="#" class="gsc_a_at">A foundation model</a>
  <div class="gs_gray">X Y, A Lovelace, ...</div>
  <div class="gs_gray">The Journal of Things 163 (18), 2025</div></td>
  <td class="gsc_a_c"><a href="#" class="gsc_a_ac gs_ibl">1268</a></td>
  <td class="gsc_a_y"><span class="gsc_a_h gsc_a_hc gs_ibl">2025</span></td></tr>
<tr class="gsc_a_tr"><td class="gsc_a_t"><a href="#" class="gsc_a_at">Quantum regression</a>
  <div class="gs_gray">A Lovelace</div>
  <div class="gs_gray">arXiv e-prints, arXiv: 2601.11942, 2026</div></td>
  <td class="gsc_a_c"><a href="#" class="gsc_a_ac gs_ibl"></a></td>
  <td class="gsc_a_y"><span class="gsc_a_h gsc_a_hc gs_ibl">2026</span></td></tr>
</tbody></table></body></html>"""


def test_parse_name_rows_year_and_arxiv_ids():
    out = S.parse(FIXTURE)
    rows = out["rows"]
    assert out["name"] == "Ada Lovelace"
    assert [r["year"] for r in rows] == [2026, 2025, 2026]         # the year cell, never the 1268 citation count
    assert [r["scholar_citations"] for r in rows] == [12, 1268, None]
    assert [r["arxiv_id"] for r in rows] == ["2601.00001", None, "2601.11942"]   # "arXiv: 2601.11942" (space) too
    assert rows[0]["authors_abbrev"] == "A Lovelace, C Babbage"
    assert rows[1]["venue"].startswith("The Journal of Things")


def test_block_page_raises():
    with pytest.raises(S.ScholarBlocked):
        S.parse("<html><body>Our systems have detected unusual traffic. Please solve the CAPTCHA.</body></html>")


def test_profile_url_is_robots_compliant():
    url = S.profile_url("https://scholar.google.com/citations?hl=zh-CN&user=ExampleID0AJ&authuser=1",
                        "https://scholar.google.com/citations", 100)
    assert url.startswith("https://scholar.google.com/citations?user=ExampleID0AJ&")   # robots: Allow /citations?user=
    assert "cstart" not in url                                                        # robots: Disallow *cstart=
    assert "pagesize=100" in url and "sortby=pubdate" in url


def test_user_id_accepts_bare_id_and_rejects_non_profile_urls():
    assert S.user_id("ExampleID0AJ") == "ExampleID0AJ"
    with pytest.raises(ValueError):
        S.user_id("https://scholar.google.com/scholar?q=finite+element")
