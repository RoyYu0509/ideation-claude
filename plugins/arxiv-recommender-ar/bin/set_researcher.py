#!/usr/bin/env python3
"""set_researcher.py — read (--get) or write the `researcher.*` identity (personal_website,
s2_author_id, author_aliases, arxiv_categories) for an arxiv-recommender run.

TWO storage targets:

  --store <researcher.json>   PER-INSTANCE override under the run's DATA ROOT (preferred). A small
                              JSON doc {"researcher": {..}} that scripts/lib/config.py layers OVER
                              the shared plugin config.yaml. This is what lets two external folders
                              run two DIFFERENT researchers off ONE shared, untouched config.yaml.
                              Writes are a plain JSON merge (the file is generated — no comments to
                              preserve). JSON (not YAML) so a bare `python3` without PyYAML still works.

  --config <config.yaml>      LEGACY: surgical, comment-preserving line edit of the plugin config.yaml
                              `researcher:` block (replaces ONLY the targeted values; never
                              re-serializes, so comments / key order / s2_api_key stay intact). Kept
                              for the in-monorepo path and as the --get fallback (the owner default).

USED BY the arxiv-scout researcher-SWITCH path (workflows/arxiv-scout.js): when the user's free-text
input names a DIFFERENT researcher, arxiv-scout repoints identity to that person (now via --store into
the data root), clears data/profile/, and rebuilds. This is the ONE sanctioned identity mutation; no
code is edited.

  --get                     print {"personal_website":..,"s2_author_id":..,"google_scholar_url":..} as
                            JSON, then exit. With a --store file, ONLY its values (a field it omits is
                            unset — scripts/lib/config.py inherits no identity into an instance); with
                            no store file, the --config owner default.
  --scholar  <url|null>     set researcher.google_scholar_url ("null" -> null)
  --website  <url|null>     set researcher.personal_website  ("null" -> null)
  --s2-id    <id|null>      set researcher.s2_author_id      ("null" -> null)
  --aliases  "A||B"         set researcher.author_aliases    (||-joined; "" -> [])
  --categories <csv|null>   set researcher.arxiv_categories  ("null" -> null; "cs.LG,math.NA" -> list)

Fail-loud (exit 2): neither --store nor --config given; or, on the legacy path, a missing config /
absent `researcher:` block / a targeted key absent from it (the strict loader needs it present).
"""
import argparse
import json
import re
import sys
from pathlib import Path

_IDENTITY_KEYS = ("personal_website", "s2_author_id", "google_scholar_url", "author_aliases", "arxiv_categories")


# ── helpers shared by both paths ──────────────────────────────────────────────
def _collect_updates(a):
    """Translate the CLI identity flags into a {key: value} dict (only flags that were given)."""
    updates = {}
    if a.website is not None:
        updates["personal_website"] = None if a.website == "null" else a.website
    if a.s2_id is not None:
        updates["s2_author_id"] = None if a.s2_id == "null" else a.s2_id
    if a.scholar is not None:
        updates["google_scholar_url"] = None if a.scholar == "null" else a.scholar
    if a.aliases is not None:
        updates["author_aliases"] = [x for x in a.aliases.split("||") if x]
    if a.categories is not None:
        updates["arxiv_categories"] = (
            None if a.categories == "null"
            else [x.strip() for x in a.categories.split(",") if x.strip()]
        )
    return updates


# ── per-instance JSON override (--store) ──────────────────────────────────────
def _store_load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _store_researcher(path):
    r = _store_load(path).get("researcher")
    return r if isinstance(r, dict) else {}


# ── legacy surgical config.yaml edit (--config) ───────────────────────────────
def _yaml_scalar(v):
    """Render a Python value as a YAML flow scalar/sequence for in-line replacement."""
    if v is None:
        return "null"
    if isinstance(v, list):
        return "[" + ", ".join('"' + str(x).replace('"', '\\"') + '"' for x in v) + "]"
    return '"' + str(v).replace('"', '\\"') + '"'


def _find_block(lines):
    """(start, end) — the researcher: block BODY line range (end exclusive), or (None, None).
    The block ends at the first column-0 line that is neither blank nor a comment (the next
    top-level key), so interleaved comment lines (e.g. the s2_api_key warning) stay in-block."""
    start = None
    for i, ln in enumerate(lines):
        if re.match(r"^researcher:\s*(#.*)?$", ln):
            start = i + 1
            break
    if start is None:
        return None, None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j] and not lines[j][0].isspace() and not lines[j].lstrip().startswith("#"):
            end = j
            break
    return start, end


def _find_key(lines, start, end, key):
    """(idx, match) for `  <key>: <value>  # comment` within the block, else (None, None).
    Groups: 1 = indent+key+colon+space, 2 = value, 3 = trailing ` # comment` (or None)."""
    pat = re.compile(r"^(\s*" + re.escape(key) + r":\s*)(.*?)(\s+#.*)?$")
    for j in range(start, end):
        m = pat.match(lines[j])
        if m:
            return j, m
    return None, None


def _config_get(config_path):
    """{personal_website, s2_author_id} read from the plugin config.yaml researcher block,
    or {} if the file/block is absent (so --get can fall back gracefully)."""
    p = Path(config_path) if config_path else None
    if not p or not p.is_file():
        return {}
    lines = p.read_text().split("\n")
    start, end = _find_block(lines)
    if start is None:
        return {}
    out = {}
    for k in ("personal_website", "s2_author_id", "google_scholar_url"):
        _, m = _find_key(lines, start, end, k)
        raw = m.group(2).strip() if m else ""
        out[k] = None if raw in ("", "null", "~") else raw.strip("\"").strip("'")
    return out


def _config_write(config_path, updates):
    p = Path(config_path)
    if not p.is_file():
        sys.exit(f"set_researcher: config not found: {p}")
    lines = p.read_text().split("\n")
    start, end = _find_block(lines)
    if start is None:
        sys.exit("set_researcher: no `researcher:` block in config")
    for key, val in updates.items():
        j, m = _find_key(lines, start, end, key)
        if m is None:
            sys.exit(f"set_researcher: key researcher.{key} not found (strict loader needs it present)")
        lines[j] = f"{m.group(1)}{_yaml_scalar(val)}{m.group(3) or ''}"
    p.write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store")   # per-instance researcher.json override (preferred read/write target)
    ap.add_argument("--config")  # plugin config.yaml (legacy surgical edit + --get default source)
    ap.add_argument("--get", action="store_true")
    ap.add_argument("--website")
    ap.add_argument("--s2-id", dest="s2_id")
    ap.add_argument("--scholar")
    ap.add_argument("--aliases")
    ap.add_argument("--categories")
    a = ap.parse_args()

    if not a.store and not a.config:
        sys.exit("set_researcher: need --store <researcher.json> or --config <config.yaml>")

    updates = _collect_updates(a)

    # ── Preferred: per-instance JSON override under the data root ──────────────
    if a.store:
        store = Path(a.store)
        if a.get:
            # an instance WITH researcher.json inherits no identity (scripts/lib/config.py): a field it
            # omits is unset; only a folder without one shows the owner default
            has_store = isinstance(_store_load(store).get("researcher"), dict)   # {"use_shared_default": true} ⇒ owner default
            r = _store_researcher(store)
            base = {} if has_store else _config_get(a.config)
            out = {}
            for k in ("personal_website", "s2_author_id", "google_scholar_url"):
                v = r.get(k) if has_store else base.get(k)
                out[k] = None if v in ("", "null", None) else v
            print(json.dumps(out))
            return
        data = _store_load(store)
        r = data.get("researcher")
        if not isinstance(r, dict):
            r = {}
        r.update(updates)
        data["researcher"] = r
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return

    # ── Legacy: surgical edit of the plugin config.yaml ───────────────────────
    if a.get:
        print(json.dumps(_config_get(a.config)))
        return
    _config_write(a.config, updates)


if __name__ == "__main__":
    main()
