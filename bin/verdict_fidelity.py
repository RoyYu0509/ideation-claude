#!/usr/bin/env python3
"""verdict_fidelity.py — mechanical verdict harvest + FINAL-REPORT verdict-fidelity check (P-3/H-17).

The deterministic teeth behind spec/research.js collectVerdicts/enforceVerdictFidelity (same pattern as
assertShipReady → bin/pipeline_status.sh: the oracle lives OUTSIDE the L0 reproduction). The prose half of
the contract is the writeFinalReport enactment comment in spec/research.js and experiment-protocol §2.3
(producer side) — field-shape changes move together there and here.

Subcommands (stdlib only, deterministic):
  collect <ws>
      → recursive glob <ws>/code/**/results/*.json; for each parseable JSON collect every STRING value
        whose dotted key path is ≤3 segments and whose key name is `verdict` or ends with `_verdict`
        (dicts only — never descends into lists, so per-cell verdicts stay out of scope); for each
        `<k>_verdict.verdict` hit, also collect its sibling BOOLEAN fields (the named load-bearing
        aggregates, e.g. ours_valid_past_vacuity_all). Unparseable or >5MB files → NON-FATAL skip, listed
        in `skipped`. stdout: JSON {"verdicts":[{"file","key","value"}...], "skipped":[{"file","reason"}...]}.
        ALWAYS exit 0 (detector discipline — a kill/abandon exit must never be blocked by this harvest).
  check <report.md> <ws>
      → re-collects from <ws>, splits the report into BODY/APPENDIX at the FIRST
        '## Machine verdicts (verbatim)' heading, then enforces:
        (i)   every deduped-by-value collected enum STRING appears verbatim in the BODY ONLY (the appendix
              always contains every enum, so a whole-file substring check would be vacuously true);
        (ii)  flattening scan, scoped PER collected verdict — NEVER a global word ban (phase0's legitimate
              enum IS "CONFIRM"): for each verdict whose value matches /(VOID|PARTIAL|SUSPECT|FAIL)/,
              derive a token mechanically from the key (<k>_verdict.verdict → <K> uppercased;
              <parent>.<name>.verdict → <name>, e.g. per_system.double_well.verdict → double_well;
              no derivable token, e.g. top-level overall_verdict → skip) and flag every BODY line that
              contains the token AND /\\b(confirmed|passed|clean|succeed(ed)?)\\b/i but NOT the enum string;
        (iii) the APPENDIX exists and carries every collected {file,key,value} row (booleans included) plus
              a note naming each skipped file.
        Empty collection (no verdicts, nothing skipped) → trivially pass: prints "none found", exit 0.
        Violations → itemized one per line on stdout, exit 1. Pass → exit 0.
"""
import glob
import json
import os
import re
import sys

MAX_BYTES = 5 * 1024 * 1024   # >5MB → skip (the audited 4.8MB E0 manifest must stay IN scope)
APPENDIX_HEADING = "## Machine verdicts (verbatim)"
BAD_ENUM_RE = re.compile(r"(VOID|PARTIAL|SUSPECT|FAIL)")
HAPPY_RE = re.compile(r"\b(confirmed|passed|clean|succeed(ed)?)\b", re.I)


def _harvest_dict(obj, path, rows):
    """Collect verdict strings at dotted key paths ≤3 segments; dicts only (lists are out of scope)."""
    if not isinstance(obj, dict) or len(path) >= 3:
        return
    for key, val in obj.items():
        if not isinstance(key, str):
            continue
        kpath = path + [key]
        if isinstance(val, str) and (key == "verdict" or key.endswith("_verdict")):
            rows.append({"key": ".".join(kpath), "value": val})
            # a `<k>_verdict.verdict` hit also carries its named load-bearing boolean siblings
            if key == "verdict" and len(path) >= 1 and path[-1].endswith("_verdict"):
                for sk, sv in obj.items():
                    if isinstance(sk, str) and isinstance(sv, bool):
                        rows.append({"key": ".".join(path + [sk]), "value": sv})
        elif isinstance(val, dict):
            _harvest_dict(val, kpath, rows)


def collect(ws):
    verdicts, skipped = [], []
    pattern = os.path.join(ws, "code", "**", "results", "*.json")
    for fp in sorted(glob.glob(pattern, recursive=True)):
        rel = os.path.relpath(fp, ws)
        try:
            if os.path.getsize(fp) > MAX_BYTES:
                skipped.append({"file": rel, "reason": "over-5MB"})
                continue
            with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            skipped.append({"file": rel, "reason": type(exc).__name__})
            continue
        rows = []
        _harvest_dict(data, [], rows)
        for row in rows:
            verdicts.append({"file": rel, "key": row["key"], "value": row["value"]})
    return {"verdicts": verdicts, "skipped": skipped}


def derive_token(key):
    """Mechanical flattening-token from a dotted key. k2_verdict.verdict → K2;
    <parent>.<name>.verdict → <name>; anything else (overall_verdict, ...) → None (skip)."""
    segs = key.split(".")
    if len(segs) >= 2 and segs[-1] == "verdict" and segs[-2].endswith("_verdict"):
        stem = segs[-2][: -len("_verdict")]
        return stem.upper() or None
    if len(segs) == 3 and segs[-1] == "verdict":
        return segs[1]
    return None


def check(report_path, ws):
    harvest = collect(ws)
    verdicts, skipped = harvest["verdicts"], harvest["skipped"]
    if not verdicts and not skipped:
        print("PASS: none found (no machine verdicts under code/**/results/*.json — trivially consistent)")
        return 0
    try:
        with open(report_path, "r", encoding="utf-8", errors="replace") as fh:
            report = fh.read()
    except OSError as exc:
        print("VIOLATION(report): cannot read %s (%s)" % (report_path, type(exc).__name__))
        return 1

    idx = report.find(APPENDIX_HEADING)
    body = report if idx < 0 else report[:idx]
    appendix = None if idx < 0 else report[idx:]
    body_lines = body.splitlines()

    violations = []
    enum_rows = [r for r in verdicts if isinstance(r["value"], str)]

    # (i) every deduped enum value verbatim in BODY ONLY
    seen = set()
    for row in enum_rows:
        val = row["value"]
        if val in seen:
            continue
        seen.add(val)
        if val not in body:
            violations.append(
                "CLAUSE(i): enum '%s' (%s :: %s) does not appear verbatim in the report BODY"
                % (val, row["file"], row["key"]))

    # (ii) per-verdict flattening scan (token + happy-word without the enum), never a global word ban
    flagged = set()
    for row in enum_rows:
        val = row["value"]
        if not BAD_ENUM_RE.search(val):
            continue
        token = derive_token(row["key"])
        if not token:
            continue
        tok_re = re.compile(r"\b" + re.escape(token), re.I)
        for n, line in enumerate(body_lines, 1):
            if tok_re.search(line) and HAPPY_RE.search(line) and val not in line:
                sig = (val, n)
                if sig in flagged:
                    continue
                flagged.add(sig)
                violations.append(
                    "CLAUSE(ii): BODY line %d characterizes %s (%s) as confirmed/passed/clean without its enum '%s': %s"
                    % (n, token, row["key"], val, line.strip()))

    # (iii) appendix exists + carries every row + names every skipped file
    if appendix is None:
        violations.append("CLAUSE(iii): appendix heading '%s' missing from the report" % APPENDIX_HEADING)
    else:
        for row in verdicts:
            val_str = "true" if row["value"] is True else "false" if row["value"] is False else str(row["value"])
            if not any(row["key"] in line and val_str in line for line in appendix.splitlines()):
                violations.append(
                    "CLAUSE(iii): appendix row missing: %s :: %s = %s" % (row["file"], row["key"], val_str))
        for sk in skipped:
            if sk["file"] not in appendix:
                violations.append(
                    "CLAUSE(iii): appendix skipped-note missing for unreadable manifest: %s (%s)"
                    % (sk["file"], sk["reason"]))

    if violations:
        for v in violations:
            print(v)
        return 1
    print("PASS: %d verdict row(s) consistent (%d enum value(s) verbatim in BODY, appendix complete)"
          % (len(verdicts), len(seen)))
    return 0


def main(argv):
    if len(argv) >= 3 and argv[1] == "collect":
        print(json.dumps(collect(argv[2]), indent=1))
        return 0                                            # detector discipline: collect ALWAYS exits 0
    if len(argv) >= 4 and argv[1] == "check":
        return check(argv[2], argv[3])
    print("usage: verdict_fidelity.py collect <ws> | check <report.md> <ws>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
