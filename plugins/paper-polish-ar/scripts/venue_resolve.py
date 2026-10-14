#!/usr/bin/env python3
r"""Deterministic venue-anchor resolution for /review and /polish (the file-system facts only).

This replaces the duplicated, slowly-drifting venuePack / venueReady≈venueHasProfile / resolveVenue /
listPreparedVenues bash+JS that lived in both spec/review.js and spec/polish.js. The ONE intentional
difference between the two callers is made EXPLICIT by --require-review-kit:

  /review  needs BOTH a profile.md AND a review/ kit (review/rubric.md = the axes + bar)  -> pass the flag
  /polish  needs only a profile.md (register + acceptance bar)                            -> omit the flag

The JUDGMENT steps that pick/recommend a venue stay in the spec (they call an agent / AskUserQuestion):
recommendVenue (a reviewer subagent reads the title/abstract), runVenuePicker (AskUserQuestion), and
venuePreamble (the goal preamble). They consume this script's `list` (the picker universe) and `pack`
(materialize the chosen venue) outputs.

--root is the PLUGIN root (venue anchors live under <root>/skills/house-style/examples/venue-anchors).

Subcommands (all emit JSON on stdout):
  resolve --root R --venue V [--field F] [--require-review-kit]
      The discriminated resolveVenue result the Phase-0 driver acts on:
        {"status":"ok"|"venue-only", ...pack}   use it
        {"status":"missing", "requested": "<v/f>"}   ABORT (unsupported / no kit)
        {"status":"needs-picker"}   no venue named -> recommend + AskUserQuestion picker
      (--venue may be omitted / empty to force needs-picker.)
  list    --root R [--require-review-kit]
      {"prepared": [<rel>, ...]} — every <venue>[/<field>] with a profile.md (and a review/ kit when
      the flag is set), EXCLUDING default / _TEMPLATE / */_core. The picker universe + the set a named
      venue is validated against.
  pack    --root R --rel REL --label LABEL --status STATUS
      The venuePack for an already-chosen REL (full path from root, e.g.
      "skills/house-style/examples/venue-anchors/SIAM/SISC"). Used by runVenuePicker after the user picks.

A pack is: {label, dir, profile, reviewDir, status, coreDir, coreProfile}. coreDir/coreProfile are set
when a sibling `_core/profile.md` exists (a sub-brand OVERLAY that COMPOSES over a shared CORE).
"""
import argparse
import glob
import json
import os
import sys

VENUE_BASE = "skills/house-style/examples/venue-anchors"


def isfile(*parts):
    return os.path.isfile(os.path.join(*parts))


def ready(root, rel, require_kit):
    """venueReady (require_kit) / venueHasProfile (not require_kit)."""
    if not isfile(root, rel, "profile.md"):
        return False
    if require_kit and not isfile(root, rel, "review", "rubric.md"):
        return False
    return True


def venue_pack(root, rel, label, status):
    parent = "/".join(rel.split("/")[:-1])
    core_rel = (parent + "/_core") if parent else None
    core_dir = core_profile = None
    if core_rel and isfile(root, core_rel, "profile.md"):
        core_dir = core_rel
        core_profile = core_rel + "/profile.md"
    return {
        "label": label,
        "dir": rel,
        "profile": rel + "/profile.md",
        "reviewDir": rel + "/review",
        "status": status,
        "coreDir": core_dir,
        "coreProfile": core_profile,
    }


def resolve_venue(root, venue, field, require_kit):
    def rel(v, f):
        return "%s/%s/%s" % (VENUE_BASE, v, f) if f else "%s/%s" % (VENUE_BASE, v)

    if not venue:
        return {"status": "needs-picker"}
    if ready(root, rel(venue, field), require_kit):
        label = ("%s/%s" % (venue, field)) if field else venue
        return venue_pack(root, rel(venue, field), label, "ok")
    if field and ready(root, rel(venue, None), require_kit):
        return venue_pack(root, rel(venue, None), venue, "venue-only")
    return {"status": "missing", "requested": ("%s/%s" % (venue, field)) if field else venue}


def list_prepared(root, require_kit):
    base = os.path.join(root, VENUE_BASE)
    found = []
    for pat in (os.path.join(base, "*", "profile.md"), os.path.join(base, "*", "*", "profile.md")):
        for p in sorted(glob.glob(pat)):   # deterministic order (the original relied on shell glob's sort)
            d = os.path.dirname(p)
            if require_kit and not os.path.isfile(os.path.join(d, "review", "rubric.md")):
                continue
            rel = os.path.relpath(d, base)
            top = rel.split("/")[0]
            if rel in ("default", "_TEMPLATE") or rel.endswith("/_core"):
                continue
            if top in ("default", "_TEMPLATE"):
                continue
            found.append(rel)
    # stable de-dup
    seen, out = set(), []
    for r in found:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("resolve")
    pr.add_argument("--root", required=True)
    pr.add_argument("--venue", default=None)
    pr.add_argument("--field", default=None)
    pr.add_argument("--require-review-kit", action="store_true")

    pl = sub.add_parser("list")
    pl.add_argument("--root", required=True)
    pl.add_argument("--require-review-kit", action="store_true")

    pp = sub.add_parser("pack")
    pp.add_argument("--root", required=True)
    pp.add_argument("--rel", required=True)
    pp.add_argument("--label", required=True)
    pp.add_argument("--status", required=True)

    args = ap.parse_args()
    if args.cmd == "resolve":
        out = resolve_venue(args.root, args.venue or None, args.field or None, args.require_review_kit)
    elif args.cmd == "list":
        out = {"prepared": list_prepared(args.root, args.require_review_kit)}
    elif args.cmd == "pack":
        out = venue_pack(args.root, args.rel, args.label, args.status)
    else:
        sys.stderr.write("venue_resolve: unknown subcommand\n")
        raise SystemExit(2)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
