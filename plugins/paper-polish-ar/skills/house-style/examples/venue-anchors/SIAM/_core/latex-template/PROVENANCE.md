# SIAM LaTeX Template — Provenance

Fetched: 2026-06-18

---

## Files actually fetched (verbatim, not summarized)

### `siamart220329.cls`
- **Version**: v1.4.4 (2022/03/29)
- **Lines**: 1915
- **Source URL**: https://raw.githubusercontent.com/facebookresearch/latticer/main/tex/siamart220329.cls
- **Mirror origin**: facebookresearch/latticer (GitHub), which re-distributes the official SIAM macro package
- **Official SIAM source**: https://epubs.siam.org/pb-assets/macros/standard/siamart220329.cls (returns 403 to curl without browser headers)
- **License**: MIT License (as declared by Meta in the latticer repo wrapper). The underlying SIAM class is distributed under SIAM's own terms: "You are NOT ALLOWED to change this file. You are NOT ALLOWED to distribute this file alone." Distribution must accompany the complete macro package.
- **Integrity check**: File starts with `%% This is file 'siamart220329.cls', based on article.cls` and ends with `%% End of file 'siamart220329.cls'.` — complete.

### `siamplain.bst`
- **Lines**: 1157
- **Source URL**: https://raw.githubusercontent.com/facebookresearch/latticer/main/tex/siamplain.bst
- **Mirror origin**: facebookresearch/latticer (GitHub)
- **Official SIAM source**: https://epubs.siam.org/pb-assets/macros/standard/siamplain.bst (returns 403 to curl)
- **License**: MIT License (Meta wrapper); underlying SIAM terms as above.
- **Integrity check**: File starts with `% ====================== SIAM.BST ================================ %` and ends with `EXECUTE {end.bib}` — complete.

### `ex_article.tex`
- **Lines**: 234
- **Source URL**: https://raw.githubusercontent.com/danoan/gf-paper/master/SIAM/ex_article.tex
- **Mirror origin**: danoan/gf-paper (GitHub), which contains the full `siamart_220329.zip` distribution
- **License**: SIAM macro package terms (see above). Template files may be freely adapted.
- **Notes**: Uses `\documentclass[review,hidelinks,onefignum,onetabnum]{siamart220329}` and `\input{ex_shared}`.

### `ex_shared.tex`
- **Lines**: 50
- **Source URL**: https://raw.githubusercontent.com/danoan/gf-paper/master/SIAM/ex_shared.tex
- **Mirror origin**: danoan/gf-paper (GitHub)
- **License**: SIAM macro package terms (see above).
- **Notes**: Contains shared title/author/header macros used by both article and supplement.

### `ex_supplement.tex`
- **Lines**: 75
- **Source URL**: https://raw.githubusercontent.com/danoan/gf-paper/master/SIAM/ex_supplement.tex
- **Mirror origin**: danoan/gf-paper (GitHub)
- **License**: SIAM macro package terms (see above).
- **Notes**: Uses `\documentclass[review,supplement,hidelinks,onefignum,onetabnum]{siamart220329}`.

### `references.bib`
- **Lines**: 140
- **Source URL**: https://raw.githubusercontent.com/danoan/gf-paper/master/SIAM/references.bib
- **Mirror origin**: danoan/gf-paper (GitHub)
- **Notes**: SIAM sample bibliography showing DOI, URL, arXiv eprint, and article-ID fields.

### `ex_article_reference.tex`
- **Lines**: 1106
- **Source URL**: https://raw.githubusercontent.com/facebookresearch/latticer/main/tex/paper.tex
- **Notes**: A real published SIAM paper (latticer) using siamart220329. Useful as a full working example.
- **License**: MIT License (Meta Platforms, Inc.)

---

## Files authored in this repo (not fetched)

### `main.tex`
- Self-contained article skeleton using `\documentclass{siamart220329}`.
- All SIAM front-matter placeholders present: `\title`, `\author`+`\thanks`, `abstract`, `keywords`, `MSCcodes`, `\maketitle`, stub sections (Introduction / Methods / Numerical experiments / Conclusions), appendix, `\section*{Acknowledgments}`, `\bibliographystyle{siamplain}\bibliography{references}`.
- Compiles with: `pdflatex main && bibtex main && pdflatex main && pdflatex main`

### `stub_references.bib`
- Minimal bibliography stub for main.tex. Replace with real entries following the format in `references.bib`.

---

## Files NOT fetched (unavailable or blocked)

| File | Reason |
|------|--------|
| `siamart251216.cls` (v1.4.8, Dec 2025, the newest version) | SIAM's epubs.siam.org returns HTTP 403 to curl; no public GitHub mirror found as of 2026-06-18. Drop in manually from https://epubs.siam.org/pb-assets/macros/standard/siamart251216.cls (browser download works). |
| `siamonline220329.cls` | Not in the danoan/gf-paper or facebookresearch/latticer mirrors; SIAM 403 block. Manual download from the SIAM zip if needed. |
| `docsiamart.tex` / `docsiamart.pdf` | Available at https://epubs.siam.org/pb-assets/macros/standard/docsiamart.tex — the fetched content showed it uses `siamart251216`, not `siamart220329`. Omitted to avoid version mismatch; retrieve manually if needed. |
| `lexample_fig1.eps`, `lexample_fig2.eps` | EPS figure assets; not needed for skeleton compilation. Available in danoan/gf-paper SIAM directory if required. |
| `data.dat` | PGFPlots data file for docsiamart examples; not needed for skeleton. |

---

## Version note

The **current** SIAM class as of December 2025 is `siamart251216` (v1.4.8). The fetched class is `siamart220329` (v1.4.4, March 2022). The newer version adds margin adjustments for print vendors, a cleveref fix, and changes "AMS subject classifications" to "MSC codes". The `main.tex` skeleton already uses `\begin{MSCcodes}` (the new name), which is forward-compatible once you swap the `.cls` file. To upgrade: replace `siamart220329.cls` with `siamart251216.cls` and update the `\documentclass` line in `main.tex`.

---

## License summary

The SIAM class and BibTeX style files carry SIAM's distribution restriction: they must be distributed as part of the complete macro package and may not be modified. Template `.tex` files (ex_article, ex_shared, ex_supplement, references.bib) are freely adaptable for your own manuscripts.
