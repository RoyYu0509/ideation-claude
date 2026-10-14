"""Thin BM25 wrapper. Tokenization is intentionally simple — lowercased
unicode-word splits with a small stop-word list. The corpus is short (a week of
abstracts in one or two arXiv categories), so we don't need anything fancier."""
from __future__ import annotations

import re
from typing import Sequence

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "is", "are",
    "we", "our", "this", "that", "these", "those", "with", "by", "from", "as",
    "be", "been", "it", "its", "at", "but", "not", "us", "such", "than",
    "into", "via", "their", "they", "them", "have", "has", "had", "can", "may",
    "also", "more", "most", "much", "many", "show", "shows", "shown", "results",
    "result", "paper", "papers", "approach", "method", "methods", "novel",
    "new", "use", "uses", "used", "using", "based", "propose", "proposed",
}


def tokenize(text: str) -> list[str]:
    return [
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if t.lower() not in _STOP and len(t) > 1
    ]


# ── Phrase mode (REC-SYSTEM-V2 A4; whole-phrase matching since 2026-09-13) ───
# The legacy query splits every curated keyword into unigrams ("finite element method" →
# finite + element) and repeats a word once per thread that listed it. The first phrase mode
# (2026-09-12) kept adjacent word PAIRS, so "physics-informed neural networks" still scored its
# fragment neural_network on its own: on the W24 dev pool 307 of the 345 BM25 hits (89%)
# matched a fragment only (neural_network df 130, foundation_model 58, over_time 28), and the
# phrase report the profile agent reads could not see it. Now each curated phrase is ONE term
# that matches only where all its words occur consecutively and in order. Both sides split
# hyphens ("physics-informed" ≡ "physics informed"), fold a trailing plural s and drop only
# function words — content words such as "method" stay (the legacy stop list turned
# "quasicontinuum method" into the bare word quasicontinuum). The legacy tokenize() /
# rank(phrases=False) path is untouched so the V1 ablation arm stays reproducible.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]+")
_PHRASE_STOP = {"the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "with", "by", "from",
                "as", "at", "via", "into"}


def _stem(t: str) -> str:
    return t[:-1] if len(t) > 4 and t.endswith("s") and not t.endswith("ss") else t


def _phrase_words(text: str) -> list[str]:
    return [_stem(w) for w in (x.lower() for x in _WORD_RE.findall(text or "")) if w not in _PHRASE_STOP]


def phrase_terms(phrases: Sequence[str]) -> list[str]:
    """Query terms for a curated phrase list: each phrase is ONE term, its normalized words
    joined by '_' ("physics-informed neural networks" → physic_informed_neural_network; a
    one-word phrase stays that word). Deduplicated, first-seen order."""
    out: list[str] = []
    seen: set[str] = set()
    for ph in phrases:
        t = "_".join(_phrase_words(ph))
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def tokenize_phrases(text: str, terms: Sequence[str]) -> list[str]:
    """Document tokens for phrase mode: the words, plus one token per occurrence of each
    multi-word query term whose words appear consecutively and in order. A fragment of a
    phrase is never a token, so only whole phrases can match (and the document length stays
    ≈ its word count, as BM25's length normalization expects)."""
    words = _phrase_words(text)
    starts: dict[str, list[int]] = {}
    for i, w in enumerate(words):
        starts.setdefault(w, []).append(i)
    out = list(words)
    for t in terms:
        parts = t.split("_")
        if len(parts) > 1:
            n = len(parts)
            out.extend(t for i in starts.get(parts[0], ()) if words[i:i + n] == parts)
    return out


def rank(query_tokens: Sequence[str], docs: Sequence[str], top_k: int,
         phrases: bool = False) -> list[tuple[int, float]]:
    """BM25 over `docs`. phrases=True: query_tokens come from phrase_terms and every doc is
    tokenized with tokenize_phrases against them; False is the legacy unigram path."""
    if not docs:
        return []
    if phrases:
        tokenized_corpus = [tokenize_phrases(d, query_tokens) for d in docs]
    else:
        tokenized_corpus = [tokenize(d) for d in docs]
    bm = BM25Okapi(tokenized_corpus)
    scores = bm.get_scores(list(query_tokens))
    k = min(top_k, len(scores))
    pairs = sorted(enumerate(scores), key=lambda p: -p[1])[:k]
    return [(int(i), float(s)) for i, s in pairs]
