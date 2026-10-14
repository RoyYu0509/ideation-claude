"""Reading a profile DIRECTORY — the one I/O companion of lib/channel_spec (2026-09-16).

lib/channel_spec is pure; something still has to open the files, decide whether a companion file is present
and was built from this papers.json, and build the View. That happens here, once, for both the coverage
check (scripts/profile_finalize.py --check-only) and the ablation runtime (report-v2/ablation/profile_view.py).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import channel_spec as CS
from . import citation_graph


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_json(p: Path) -> Any:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def resolve(profile_dir: str | Path) -> Path:
    """Accept a data root or its data/profile directory."""
    d = Path(profile_dir).expanduser().resolve()
    return d if (d / "papers.json").exists() or (d / "profile.json").exists() else d / "data" / "profile"


def load_companions(pdir: Path, papers_sha: str) -> tuple[dict[str, str | None], dict | None]:
    """Companion status (None = present and built from this papers.json, else the reason) + the ref abstracts."""
    comp: dict[str, str | None] = {}
    try:
        citation_graph.load_graph(pdir / "citation-graph.json", pdir / "papers.json")
        comp["citation-graph.json"] = None
    except citation_graph.CitationGraphError as e:
        comp["citation-graph.json"] = str(e)
    ra_path, refs = pdir / "ref_abstracts.json", None
    if not ra_path.exists():
        comp["ref_abstracts.json"] = "not built — run scripts/profile_tools.py"
    else:
        doc = load_json(ra_path)
        if doc.get("papers_sha256") != papers_sha:
            comp["ref_abstracts.json"] = "built from a different papers.json — re-run scripts/profile_tools.py"
        else:
            comp["ref_abstracts.json"], refs = None, doc.get("refs") or {}
    return comp, refs


def load_view(profile_dir: str | Path, cfg) -> tuple[CS.View, dict[str, Any]]:
    """An existing (merged) profile directory → (View, provenance). Raises FileNotFoundError when
    profile.json or papers.json is absent — a directory without them is not a profile."""
    pdir = resolve(profile_dir)
    pj, pp = pdir / "profile.json", pdir / "papers.json"
    for f in (pj, pp):
        if not f.exists():
            raise FileNotFoundError(f"{f} not found — not a profile directory")
    prof, papers_doc = load_json(pj), load_json(pp)
    papers_sha = sha256_file(pp)
    comp, refs = load_companions(pdir, papers_sha)
    v = CS.view(prof, papers_doc.get("papers") or [], as_of=prof.get("as_of") or papers_doc.get("cutoff"),
                companions=comp, ref_abstracts=refs, params=CS.params_from_config(cfg))
    prov = {"profile_dir": str(pdir), "schema": CS.schema_kind(prof),
            "schema_version": prof.get("schema_version"), "finalized_by": prof.get("finalized_by"),
            "files": {"profile.json": sha256_file(pj), "papers.json": papers_sha},
            "companions": comp, "params": dict(v.params)}
    return v, prov
