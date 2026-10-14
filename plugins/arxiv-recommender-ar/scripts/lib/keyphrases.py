"""The BM25 channel's retrieval phrases, extracted from the researcher's own papers (2026-09-16).

Why a script and not the profile agent: on the researcher's 12-week labelled pool, phrases written by the
profile agent matched 42–123 papers of 2,574 and lost to this extractor on 15 of 15 profile builds (out-of-thread
recall +0.069, interval excluding 0 — report-v2/experiments/profile-diag/REPORT.md §6, §8.4, §8.6). The agent's
phrases are precise but rare: nobody else prints them, so whole-phrase BM25 retrieves almost nothing. Making the
agent write phrases that a recent arXiv week actually matches (the V3 arm) closed most of the gap but not all of
it, and cost 5–7 extra rounds per build.

The rule is neutral — it uses only the researcher's own papers and a background pool of recent arXiv papers,
never any relevance label:

    1. take every 1–3-word phrase from the own papers' titles + abstracts (same normalization as the BM25
       whole-phrase match: lib/bm25._phrase_words, so a phrase found here is a phrase that can match);
    2. keep the phrases that at least `min_own` of the own papers print;
    3. score own_df × log((N + 1) / (bg_df + 1)) against the background pool, and keep the top `k`.

The list is computed once per profile build (scripts/profile_finalize.py) and stored as profile.json
`keywords`, so the weekly run reads it like any other profile field.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, Sequence

from . import bm25

# Words that must not start or end a phrase: they carry no topic, and a phrase that begins or ends with one is
# a sentence fragment ("we propose", "results show") rather than a term a paper would print again.
BOUNDARY_STOP = {"show", "shows", "shown", "result", "results", "paper", "propose", "proposed", "present",
                 "study", "new", "novel", "use", "using", "used", "based", "also", "can", "may", "such", "well",
                 "which", "while", "however", "both", "each", "two", "one", "first", "second", "these", "this",
                 "that", "we", "our", "its", "their", "it", "is", "are", "be", "been", "has", "have", "not",
                 "than", "more", "most", "here", "there", "then", "thus", "where", "when", "how", "what", "all",
                 "any", "some"}
SEG = re.compile(r"[.;:,()\[\]?!]")
MIN_WORD = 5            # a one-word phrase shorter than this is never specific enough
N_MAX = 3


def phrases_of(text: str, n_max: int = N_MAX) -> set[str]:
    """Every candidate phrase in one text, within punctuation segments (a phrase never spans a comma)."""
    out: set[str] = set()
    for seg in SEG.split(text or ""):
        words = bm25._phrase_words(seg)
        for n in range(1, n_max + 1):
            for i in range(len(words) - n + 1):
                g = words[i:i + n]
                if g[0] in BOUNDARY_STOP or g[-1] in BOUNDARY_STOP:
                    continue
                if n == 1 and (len(g[0]) < MIN_WORD or g[0] in bm25._STOP):
                    continue
                out.add(" ".join(g))
    return out


def extract(own_texts: Sequence[str], bg_texts: Iterable[str], k: int = 50, min_own: int = 2) -> list[dict]:
    """Ranked retrieval phrases: [{phrase, own_df, bg_df, score}], most distinctive first."""
    own_df = Counter(p for t in own_texts for p in phrases_of(t))
    cand = {p for p, c in own_df.items() if c >= min_own}
    bg = list(bg_texts)
    bg_df = Counter(p for t in bg for p in phrases_of(t) if p in cand)
    n = len(bg)
    rows = [{"phrase": p, "own_df": own_df[p], "bg_df": bg_df.get(p, 0),
             "score": own_df[p] * math.log((n + 1) / (bg_df.get(p, 0) + 1))} for p in cand]
    rows.sort(key=lambda r: (-r["score"], r["phrase"]))
    return rows[:k]


def own_frequency_fallback(own_texts: Sequence[str], k: int = 50, min_own: int = 2) -> list[dict]:
    """No background pool (the very first profile build): rank by how many own papers print the phrase."""
    own_df = Counter(p for t in own_texts for p in phrases_of(t))
    rows = [{"phrase": p, "own_df": c, "bg_df": None, "score": float(c)} for p, c in own_df.items() if c >= min_own]
    rows.sort(key=lambda r: (-r["score"], r["phrase"]))
    return rows[:k]
