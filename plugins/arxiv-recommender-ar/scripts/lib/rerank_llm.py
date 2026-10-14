"""lib/rerank_llm.py — the LLM rerank (A0) and the thread-quota final select (G1 → TOP), shared by production
and by the ablation package.

Ported 2026-09-19 from report-v2/ablation/{rerank,units,final20}.py (修订 #8 / #11). The prompt texts, the
blinding, the paper block, the output rule, the group dealing and the repair rule live HERE and nowhere else:
report-v2/ablation imports this module, so the arm that was evaluated and the arm that runs in production
cannot drift (the ablation's `rerank.py fidelity` compares the prompt bodies byte for byte).

The contract (修订 #8 §2, unchanged):
- a candidate is shown as id / title / abstract / categories — no authors, no RRF score, no quality hints;
- presentation order = the recall (RRF) order; the opaque item ids are shuffled so an id reveals nothing;
- the prompt talks only about relevance to the researcher's research directions;
- one unit = one directory (PROMPT.txt + SPAWN.md) = one agent call; the answer is plain text, one per line;
- repair: ids not in the input are dropped, duplicates keep the first, missing ids are appended in input order;
  the repair rate (bad + duplicate + short-of-what-was-asked, over what was asked) is reported.

Production pipeline (workflows/arxiv-scout.js Phase 3, driven through scripts/rerank_llm.py):
    A0   one call reads all prefetched candidates and returns the TOP_K most relevant, in order
    G1   the TOP_K are dealt round-robin into G = ceil(PROMOTE_TARGET / T) groups; one call per group picks,
         for every profile thread, the single most relevant paper in that group (or none)
    TOP  one call ranks the promoted papers and returns the k best (k = scout.rerank_return_n); a short list
         is padded from A0's order. The thread label of a paper is the thread G1 picked it for.
Every unit is crash-resumable: build_* skips a unit whose .out.json exists; collect_* is the only reader of
RESULT.txt. Nothing here calls a model — the caller spawns the agent with the SPAWN.md text.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

from lib import channel_spec as CS

TOP_K = 100                       # A0 returns this many (修订 #8 §3:精排 300 → 100)
PROMOTE_TARGET = 40               # G1: number of groups = ceil(40 / number of threads)

# ── the frozen prompt texts (修订 #8 附录 A; SHA recorded by every run) ──
PROMPT_A0 = ("Read the researcher profile and the candidate papers (id, title, abstract, categories). "
             "Rank the candidates by how relevant each is to this researcher's research directions, "
             "most relevant first. Output the ids of the {k} most relevant papers in order, one per line.")
PROMPT_L1 = ("Below are a researcher profile and a list of candidate papers, each with an id. "
             "Rank all of these papers by how relevant each is to the researcher's research directions, "
             "most relevant first. Output every id exactly once, in order, one per line.")
PROMPT_G1 = ("Below are a researcher profile listing its research threads, and a group of candidate papers. "
             "For each thread, pick the one paper in this group most relevant to that thread; if no paper in "
             "the group is relevant to a thread, pick none for it. A paper may be picked for at most one "
             "thread. Output one line per pick: thread name, a tab, paper id.")
PROMPT_G0 = ("Below are a researcher profile and a group of candidate papers. Pick the {m} papers in this "
             "group most relevant to the researcher's research directions. Output their ids, one per line.")
PROMPT_TOP = ("Below are a researcher profile and a list of finalist papers. Choose the {k} papers most "
              "relevant to the researcher's research directions and rank them, most relevant first. "
              "Output the {k} ids in order, one per line.")

SPAWN_FILE = """Read exactly ONE file: {prompt}
It contains the complete task. Follow it to the letter. Do not list directories,
do not run commands, do not search the web, do not read any other file.
Write your output to {out} exactly as the file instructs, then reply with only
the DONE line it asks for.
"""

OUT_RULE = """

## Output

Write your answer to {out} as plain text, {shape}
Nothing else in the file: no headings, no commentary, no code fences, no blank lines.

When finished reply with only the line
  DONE {out_name} written
"""
OUT_MARKER = "\n\n## Output\n"    # everything before it is the task body; only the file path after it varies


# ────────────────────────── one: blinding, paper text, output reading ──────────────────────────

def sha16(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def est_tokens(text: str) -> int:
    """Same estimate as the W35 gold pool build (words × 1.4); chars/4 overestimates scientific text by ~30%."""
    return round(len(text.split()) * 1.4)


def blind(ids: list[str], prefix: str, seed: int) -> tuple[dict[str, str], dict[str, str]]:
    """paper → opaque item id. Returns (arxiv_id → item_id, item_id → arxiv_id).

    The PRESENTATION order is not shuffled (修订 #8 §2: input order = the recall's RRF order); only the
    assignment of numbers is — otherwise `X-0001` would hand the RRF rank straight back to the model.
    """
    n = len(ids)
    perm = list(range(1, n + 1))
    random.Random(seed).shuffle(perm)
    to_item = {a: f"{prefix}-{perm[i]:04d}" for i, a in enumerate(ids)}
    return to_item, {v: k for k, v in to_item.items()}


def paper_block(cand: dict[str, Any], item_id: str) -> str:
    """Everything the model sees about one paper: id, title, abstract, categories (修订 #8 §2 removed the
    authors and every quality hint)."""
    cats = cand.get("categories") or []
    if isinstance(cats, str):
        cats = [c.strip(" '\"[]") for c in cats.split(",")]
    return (f"### {item_id}\nTitle: {cand['title']}\n"
            f"Categories: {', '.join(cats) or cand.get('primary_category', '')}\n"
            f"Abstract: {cand['abstract']}")


def papers_block(cands: list[dict[str, Any]], item_ids: list[str]) -> str:
    return "\n\n".join(paper_block(c, i) for c, i in zip(cands, item_ids))


def read_lines(path: Path) -> list[str]:
    """One entry per line; strips the numbering / bullets / code fences a model tends to add."""
    out = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        s = raw.strip().strip("`").strip()
        if not s or s.startswith("```"):
            continue
        for lead in ("- ", "* "):
            if s.startswith(lead):
                s = s[len(lead):].strip()
        if "." in s.split(" ")[0] and s.split(".")[0].isdigit():      # "12. X-0007"
            s = s.split(".", 1)[1].strip()
        out.append(s)
    return out


def repair(raw: list[str], order_in: list[str], key: dict[str, str] | None = None,
           want: int | None = None) -> dict[str, Any]:
    """The model's list of ids → a legal complete permutation (修订 #8 §2 repair rule).

    `order_in` is this step's input order (arxiv_id); `key` maps opaque ids back; `want` is how many the step
    ASKED for (A0 reads 300 and returns 100; default = the input size). repair_rate = (not-in-input + duplicate
    + short of `want`) / want. Missing ids are always appended to `full` in input order — being short only
    counts below `want`.
    """
    allowed = set(order_in)
    mapped = [(key or {}).get(x, x) for x in raw]
    seen: set[str] = set()
    order: list[str] = []
    n_bad = n_dupes = 0
    for a in mapped:
        if a not in allowed:
            n_bad += 1
            continue
        if a in seen:
            n_dupes += 1
            continue
        seen.add(a)
        order.append(a)
    missing = [a for a in order_in if a not in seen]
    full = order + missing
    want = len(order_in) if want is None else min(want, len(order_in))
    short = max(0, want - len(order))
    return {"order": order, "full": full, "n_raw": len(raw), "n_given": len(order), "want": want,
            "n_bad": n_bad, "n_dupes": n_dupes, "n_missing": len(missing), "n_short": short,
            "repair_rate": (n_bad + n_dupes + short) / max(want, 1)}


def read_pairs(path: Path, allowed_left: set[str], key: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """A G1 group's answer: one line 'thread name <tab> paper id' (falls back to the last whitespace)."""
    out = []
    for s in read_lines(path):
        left, right = (s.split("\t", 1) + [""])[:2] if "\t" in s else (s.rsplit(None, 1) + [""])[:2]
        left, right = left.strip(), right.strip()
        if not right:
            continue
        aid = (key or {}).get(right, right)
        if left in allowed_left:
            out.append((left, aid))
    return out


# ────────────────────────── two: the profile as the model sees it ──────────────────────────

def thread_keywords(v: CS.View) -> dict[str, list[str]]:
    """A v3 thread has no keywords of its own: the union of its member papers' note keywords."""
    by_key = {str(n.get("key")): (n.get("keywords") or []) for n in CS.notes(v)}
    out: dict[str, list[str]] = {}
    for t in CS.threads(v):
        kws: list[str] = []
        for k in t.get("papers") or []:
            for w in by_key.get(str(k), []):
                if w not in kws:
                    kws.append(w)
        out[t.get("name") or t.get("label") or ""] = kws
    return out


def thread_names(v: CS.View) -> list[str]:
    return [name for _, name, _ in CS.thread_members(v)]


def profile_block(v: CS.View, pdir: Path) -> str:
    """profile.md + every thread's name / summary / keywords / member titles (修订 #8 §2: the same block for
    every arm)."""
    md = (Path(pdir) / "profile.md").read_text(encoding="utf-8").strip()
    kws = thread_keywords(v)
    lines = []
    for i, name, mem in CS.thread_members(v):
        t = next((x for x in CS.threads(v) if (x.get("name") or x.get("label")) == name), {})
        lines.append(f"### Thread {i}: {name}")
        if t.get("summary"):
            lines.append(f"Summary: {t['summary']}")
        if kws.get(name):
            lines.append(f"Keywords: {', '.join(kws[name])}")
        lines.append("Papers: " + "; ".join(p.get("title", "") for p in mem))
    return f"## Researcher profile\n\n{md}\n\n## Research threads\n\n" + "\n".join(lines)


def thread_query_texts(v: CS.View) -> list[tuple[str, str]]:
    """The cross-encoder arm's queries (ablation N1): one sentence per thread 'name. summary keywords'."""
    kws = thread_keywords(v)
    out = []
    for _, name, _ in CS.thread_members(v):
        t = next((x for x in CS.threads(v) if (x.get("name") or x.get("label")) == name), {})
        out.append((name, f"{name}. {t.get('summary') or ''} {' '.join(kws.get(name, []))}".strip()))
    return out


def compose_prompt(head: str, v: CS.View, pdir: Path, cands: list[dict[str, Any]], items: list[str],
                   out_path: Path, shape: str) -> str:
    """The whole prompt of one unit: task sentence + profile block + this step's candidates + output rule."""
    return (f"{head}\n\n{profile_block(v, pdir)}\n\n## Candidate papers\n\n"
            + papers_block(cands, items)
            + OUT_RULE.format(out=out_path, out_name=Path(out_path).name, shape=shape))


def prompt_body(prompt: str) -> str:
    """The task-bearing part of a prompt — everything before the output rule (whose file path is the only
    thing that legitimately differs between the ablation unit and the production unit)."""
    return prompt.split(OUT_MARKER, 1)[0]


def body_sha(prompt: str) -> str:
    return sha16(prompt_body(prompt))


# ────────────────────────── three: G1's dealing ──────────────────────────

def n_groups(n_threads: int, promote_target: int = PROMOTE_TARGET) -> int:
    return max(1, math.ceil(promote_target / max(n_threads, 1)))


def deal(ids: list[str], G: int) -> list[list[str]]:
    """Round-robin by rank: rank i (1-based) goes to group ((i−1) mod G) + 1; A0's order is kept inside a group."""
    return [[a for j, a in enumerate(ids) if j % G == g] for g in range(G)]


# ────────────────────────── four: units on disk ──────────────────────────

def _dump(obj: Any, p: Path) -> Path:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return p


def _load(p: Path) -> Any:
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_unit(d: Path, prompt: str, out_name: str = "RESULT.txt", **meta) -> dict[str, Any]:
    """One directory per call: PROMPT.txt (the whole task) + SPAWN.md (how the caller hands it to an agent)."""
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    (d / "PROMPT.txt").write_text(prompt, encoding="utf-8")
    (d / "SPAWN.md").write_text(SPAWN_FILE.format(prompt=d / "PROMPT.txt", out=d / out_name), encoding="utf-8")
    return {"dir": str(d), "spawn": str(d / "SPAWN.md"), "expects": str(d / out_name),
            "prompt_sha256": sha16(prompt), "body_sha256": body_sha(prompt), "prompt_chars": len(prompt),
            "est_input_tok": est_tokens(prompt), **meta}


class Stage:
    """The production layout under one directory (data/cache/week-<W>-rerank-llm/):

        key.json            the blinding key (arxiv_id ↔ item id), shared by every unit of the week
        A0/  A0.in.json  A0.out.json           the single A0 unit, its input record, its collected answer
        G1-gNN/  G1-gNN.in.json  G1-gNN.out.json   one per group;  G1.plan.json = the dealing
        TOP/ TOP.in.json TOP.out.json           the final ranking call
        final.json                              what the rest of the pipeline reads
    """

    def __init__(self, out_dir: Path, week: str, v: CS.View, pdir: Path, cands: list[dict[str, Any]]):
        self.dir, self.week, self.v, self.pdir = Path(out_dir), week, v, Path(pdir)
        self.cands = cands                                     # the prefetched pool, in recall (RRF) order
        self.by_id = {c["arxiv_id"]: c for c in cands}
        self.ids = [c["arxiv_id"] for c in cands]

    # ── key ──
    def key(self, seed: int | None = None, to_item: dict[str, str] | None = None) -> dict[str, Any]:
        p = self.dir / "key.json"
        if p.exists():
            return _load(p)
        if to_item is None:
            seed = int(hashlib.sha256(self.week.encode()).hexdigest()[:8], 16) if seed is None else seed
            to_item, _ = blind(self.ids, prefix="P", seed=seed)
        k = {"to_item": to_item, "to_arxiv": {v: a for a, v in to_item.items()}, "seed": seed}
        _dump(k, p)
        return k

    def _in(self, unit: str) -> Path:
        return self.dir / f"{unit}.in.json"

    def _out(self, unit: str) -> Path:
        return self.dir / f"{unit}.out.json"

    def _build(self, unit: str, order_in: list[str], head: str, shape: str, want: int, **meta) -> dict[str, Any]:
        """Write one unit unless its answer is already collected. Returns the spawn record (+ done flag)."""
        if self._out(unit).exists():
            return {"unit": unit, "done": True, **_load(self._out(unit)).get("summary", {})}
        key = self.key()
        items = [key["to_item"][a] for a in order_in]
        d = self.dir / unit
        prompt = compose_prompt(head, self.v, self.pdir, [self.by_id[a] for a in order_in], items,
                                d / "RESULT.txt", shape)
        rec = write_unit(d, prompt, unit=unit, **meta)
        _dump({"unit": unit, "order_in": order_in, "items": items, "want": want, "prompt_sha256": rec["prompt_sha256"],
               "body_sha256": rec["body_sha256"]}, self._in(unit))
        return {"unit": unit, "done": False, "spawn": rec["spawn"], "expects": rec["expects"],
                "est_input_tok": rec["est_input_tok"], "n_in": len(order_in), "want": want}

    def _collect(self, unit: str, max_repair: float) -> dict[str, Any]:
        st = _load(self._in(unit))
        exp = self.dir / unit / "RESULT.txt"
        if not exp.exists():
            raise SystemExit(f"[rerank_llm] {unit}: {exp} not written — the agent did not finish the unit")
        rep = repair(read_lines(exp), st["order_in"], self.key()["to_arxiv"], want=st.get("want"))
        if rep["repair_rate"] > max_repair:
            n = len(list(exp.parent.glob("RESULT.rejected-*.txt"))) + 1
            exp.rename(exp.with_name(f"RESULT.rejected-{n}.txt"))
            raise SystemExit(f"[rerank_llm] {unit}: repair rate {rep['repair_rate']:.1%} > {max_repair:.0%} — answer "
                             f"moved aside as RESULT.rejected-{n}.txt; re-run the unit (exit 3)")
        return rep

    # ── A0 ──
    def build_a0(self, k: int = TOP_K) -> dict[str, Any]:
        return self._build("A0", self.ids, PROMPT_A0.format(k=k),
                           f"the ids of the {k} most relevant papers in order, one per line.", want=k, arm="A0")

    def collect_a0(self, max_repair: float = 0.05) -> dict[str, Any]:
        rep = self._collect("A0", max_repair)
        summ = {"n_given": rep["n_given"], "want": rep["want"], "repair_rate": rep["repair_rate"],
                "n_bad": rep["n_bad"], "n_dupes": rep["n_dupes"], "n_short": rep["n_short"]}
        _dump({"unit": "A0", **rep, "summary": summ}, self._out("A0"))
        return summ

    def pass_through(self, k: int = TOP_K) -> dict[str, Any]:
        """scout.rerank_pass = none (production since 2026-09-19 修订 #12): no LLM rerank — the fused mechanical
        order's first k papers are what G1 deals. Recorded in the same A0.out.json slot so every later step reads one
        place; `summary.pass == "none"` marks that no call was made."""
        summ = {"pass": "none", "n_given": min(k, len(self.ids)), "want": min(k, len(self.ids)), "repair_rate": 0.0}
        if not self._out("A0").exists():
            _dump({"unit": "A0", "order": self.ids[:k], "full": list(self.ids), "want": min(k, len(self.ids)),
                   "note": "rerank_pass=none: the recall (RRF) order, no LLM call", "summary": summ}, self._out("A0"))
        return {"unit": "A0", "done": True, **summ}

    def order100(self) -> list[str]:
        p = self._out("A0")
        if not p.exists():
            raise SystemExit("[rerank_llm] A0 not collected yet — run collect-a0 first")
        d = _load(p)
        return d["full"][:d["want"]]

    # ── G1 ──
    def build_g1(self, promote_target: int = PROMOTE_TARGET) -> dict[str, Any]:
        ids100 = self.order100()
        names = thread_names(self.v)
        G = n_groups(len(names), promote_target)
        groups = deal(ids100, G)
        _dump({"n_threads": len(names), "threads": names, "n_groups": G, "groups": groups,
               "promote_target": promote_target}, self.dir / "G1.plan.json")
        units = [self._build(f"G1-g{g:02d}", grp, PROMPT_G1, "one line per pick: thread name, a tab, paper id.",
                             want=len(grp), arm="G1", step=f"g{g:02d}") for g, grp in enumerate(groups)]
        return {"n_threads": len(names), "n_groups": G, "group_sizes": [len(x) for x in groups], "units": units}

    def collect_g1(self) -> dict[str, Any]:
        plan = _load(self.dir / "G1.plan.json")
        allowed = set(plan["threads"])
        key = self.key()["to_arxiv"]
        promoted: list[str] = []
        thread_of: dict[str, str] = {}
        n_lines = 0
        for g, grp in enumerate(plan["groups"]):
            unit = f"G1-g{g:02d}"
            exp = self.dir / unit / "RESULT.txt"
            if not exp.exists():
                raise SystemExit(f"[rerank_llm] {unit}: {exp} not written — the agent did not finish the unit")
            picks, seen_t, seen_p = [], set(), set()
            for t, a in read_pairs(exp, allowed, key):
                n_lines += 1
                if a not in grp or t in seen_t or a in seen_p:         # one paper per thread, one thread per paper
                    continue
                picks.append((t, a)); seen_t.add(t); seen_p.add(a)
            _dump({"unit": unit, "picks": picks, "summary": {"n_picks": len(picks)}}, self._out(unit))
            for t, a in picks:
                thread_of.setdefault(a, t)
        ids100 = self.order100()
        promoted = [a for a in ids100 if a in thread_of]                 # A0's order, as in the ablation
        _dump({"promoted": promoted, "thread_of": thread_of, "n_lines": n_lines}, self.dir / "G1.out.json")
        return {"n_promoted": len(promoted), "n_groups": len(plan["groups"]), "n_lines": n_lines}

    # ── TOP ──
    def build_top(self, k: int) -> dict[str, Any]:
        g1 = _load(self.dir / "G1.out.json")
        prom = g1["promoted"]
        if not prom:
            _dump({"unit": "TOP", "order": [], "full": [], "want": 0, "n_given": 0,
                   "note": "no group picked a paper; the top call was not made", "summary": {"n_given": 0, "want": 0}},
                  self._out("TOP"))
            return {"unit": "TOP", "done": True, "n_promoted": 0, "want": 0}
        kk = min(k, len(prom))
        rec = self._build("TOP", prom, PROMPT_TOP.format(k=kk), f"the {kk} ids in order, one per line.",
                          want=kk, arm="TOP")
        return {**rec, "n_promoted": len(prom)}

    def collect_top(self, k: int, max_repair: float = 0.05) -> dict[str, Any]:
        g1 = _load(self.dir / "G1.out.json")
        if not (self._out("TOP").exists() and _load(self._out("TOP")).get("want") == 0):
            rep = self._collect("TOP", max_repair)
            _dump({"unit": "TOP", **rep, "summary": {"n_given": rep["n_given"], "want": rep["want"],
                                                       "repair_rate": rep["repair_rate"]}}, self._out("TOP"))
        top_out = _load(self._out("TOP"))
        chosen = top_out["order"][:k]
        ids100 = self.order100()
        pad = [a for a in ids100 if a not in set(chosen)][:max(0, k - len(chosen))]   # short list → A0's order
        thread_of = g1["thread_of"]
        top = ([{"arxiv_id": a, "thread": thread_of.get(a), "source": "top"} for a in chosen]
               + [{"arxiv_id": a, "thread": thread_of.get(a), "source": "pad"} for a in pad])
        rest = [a for a in ids100 if a not in {t["arxiv_id"] for t in top}] \
            + [a for a in self.ids if a not in set(ids100)]
        fin = {"week": self.week, "k": k, "n_top": len(top), "n_padded": len(pad), "top": top,
               "promoted": g1["promoted"], "order100": ids100, "rest": rest,
               "prompts": {n: sha16(t) for n, t in (("A0", PROMPT_A0.format(k=TOP_K)), ("G1", PROMPT_G1),
                                                    ("TOP", PROMPT_TOP.format(k=k)))},
               "units": {"A0": _load(self._out("A0")).get("summary"), "TOP": top_out.get("summary")}}
        p = _dump(fin, self.dir / "final.json")
        return {"final_path": str(p), "n_top": len(top), "n_padded": len(pad), "n_from_top": len(chosen),
                "top": top}
