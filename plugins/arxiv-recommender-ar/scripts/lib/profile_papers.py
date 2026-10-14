"""Helpers over papers.json records, shared by build_profile_papers / profile_finalize / prefetch."""
from __future__ import annotations

import calendar
import hashlib
import re
import unicodedata
from collections import Counter
from datetime import date
from typing import Any, Iterable

_ARXIV_CAT_RE = re.compile(r"^[a-z-]+(\.[A-Za-z-]+)?$")   # math.NA, quant-ph, cond-mat.mtrl-sci; not S2's "Physics"


def norm_title(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def jaccard(a: str, b: str) -> float:
    wa, wb = set(a.split()), set(b.split())
    if not wa and not wb:
        return 1.0
    return len(wa & wb) / len(wa | wb)


def paper_key(p: dict[str, Any]) -> str:
    """Stable id a profile thread uses to name its member papers."""
    if p.get("key"):
        return str(p["key"])
    if p.get("arxiv_id"):
        return str(p["arxiv_id"])
    if p.get("paper_id"):
        return f"s2:{p['paper_id']}"
    return "t:" + hashlib.sha1(norm_title(p.get("title") or "").encode("utf-8")).hexdigest()[:10]


def _name_tokens(name: str) -> tuple[str, ...]:
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return tuple(sorted(re.findall(r"[a-z]+", s)))


def name_key(name: str) -> tuple[str, ...]:
    """Order-, case-, accent- and punctuation-free key of a full name ("Doe, Jane" and
    "Jane Doe" share one); () for an empty name."""
    return _name_tokens(name)


def same_person(a: str, b: str) -> bool:
    """Full-name equality up to order, case, accents and punctuation
    ("Doe, Jane" == "Jane Doe"). Initials never match a full name."""
    ta, tb = name_key(a), name_key(b)
    return bool(ta) and ta == tb


def paper_date(p: dict[str, Any]) -> date | None:
    d = p.get("first_date")
    if not d:
        return None
    try:
        return date.fromisoformat(str(d)[:10])
    except ValueError:
        return None


def window_start(as_of: date, months: int) -> date:
    y, m = divmod(as_of.year * 12 + (as_of.month - 1) - months, 12)
    m += 1
    return date(y, m, min(as_of.day, calendar.monthrange(y, m)[1]))


def is_recent(p: dict[str, Any], as_of: date, months: int) -> bool:
    """First version within [as_of − months, as_of]. A year-only record counts as recent
    when its year overlaps the window (generous: never silently drops a thread)."""
    start = window_start(as_of, months)
    d = paper_date(p)
    if d:
        return start <= d <= as_of
    y = p.get("year")
    return bool(y) and start.year <= int(y) <= as_of.year


def before_cutoff(p: dict[str, Any], cutoff: date) -> tuple[bool, bool]:
    """(keep, date_uncertain). Exact first-version date when known; otherwise the year —
    a record in the cutoff's own year is kept and flagged uncertain for the owner."""
    d = paper_date(p)
    if d:
        return d < cutoff, False
    y = p.get("year")
    if y is None:
        return True, True
    y = int(y)
    if y < cutoff.year:
        return True, False
    if y == cutoff.year:
        return True, True
    return False, False


def derive_categories(papers: Iterable[dict[str, Any]], min_primary: int,
                      min_cross: int) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Real arXiv categories of the researcher's own papers: keep a category that is the
    PRIMARY of >= min_primary papers or is listed (primary or cross-list) on >= min_cross.
    Returns (chosen, per-category table)."""
    prim: Counter = Counter()
    listed: Counter = Counter()
    for p in papers:
        cats = {c for c in (p.get("categories") or []) if _ARXIV_CAT_RE.match(c or "")}
        pc = p.get("primary_category")
        if pc and _ARXIV_CAT_RE.match(pc):
            prim[pc] += 1
            cats.add(pc)
        for c in cats:
            listed[c] += 1
    chosen = [c for c in sorted(listed, key=lambda c: (-listed[c], c))
              if prim[c] >= min_primary or listed[c] >= min_cross]
    table = {c: {"primary": prim[c], "listed": listed[c], "chosen": c in chosen} for c in listed}
    return chosen, table
