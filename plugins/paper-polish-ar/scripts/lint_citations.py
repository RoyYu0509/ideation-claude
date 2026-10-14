#!/usr/bin/env python3
r"""Read-only, NON-BLOCKING dangling-citation lint (advisory only).

Every \cite / [@key] in the body that resolves to NO defined reference — neither a .bib @entry{}
(recursive under the paper dir) NOR a \bibitem{} in a manuscript — is a dangling citation (it would
compile to [?]). This surfaces a dangling the author already left in the base. It NEVER edits or
reverts; resolving it (add the real .bib entry, or drop the \cite) is the author's call. Best-effort:
any error returns []. Inclusive on DEFINED keys (scans every *.bib found) to minimize false alarms — a
key flagged here exists in no bibliography.

Input  (JSON on stdin): {"root": <paper dir>, "files": [<manuscript file>, ...]}
    root   the manuscript dir (recursively scanned for *.bib to collect DEFINED keys)
    files  the manuscript files to scan for CITED keys (already deduped; include the master)
Output (JSON on stdout): [{"key": <undefined key>, "files": [<basename>, ...]}, ...]  sorted by key.
"""
import glob
import json
import os
import re
import sys

CITE = re.compile(r"\\[a-zA-Z]*[Cc]ite[a-zA-Z]*(?:\[[^\]]*\]\s*)*\{([^}]*)\}")
MDC = re.compile(r"\[@([^\]]+)\]")
MDKEY = re.compile(r"@([A-Za-z0-9_:.\-]+)")
BIBENTRY = re.compile(r"@([A-Za-z]+)\s*\{\s*([^,\s]+)")
BIBITEM = re.compile(r"\\bibitem\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
SKIP = {"string", "comment", "preamble"}


def rd(p):
    try:
        return open(p, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""


def main():
    try:
        cfg = json.load(sys.stdin)
        root = cfg["root"]
        files = [os.path.abspath(p) for p in cfg["files"]]
        defined = set()
        for b in glob.glob(os.path.join(root, "**", "*.bib"), recursive=True):
            for ty, k in BIBENTRY.findall(rd(b)):
                if ty.lower() not in SKIP:
                    defined.add(k.strip())
        cited = {}
        for p in files:
            t = rd(p)
            for k in BIBITEM.findall(t):
                defined.add(k.strip())
            ks = []
            for grp in CITE.findall(t):
                ks += [k.strip() for k in grp.split(",") if k.strip()]
            for grp in MDC.findall(t):
                ks += [k.strip() for k in MDKEY.findall("@" + grp) if k.strip()]
            for k in ks:
                cited.setdefault(k, set()).add(os.path.basename(p))
        out = [{"key": k, "files": sorted(v)} for k, v in sorted(cited.items()) if k not in defined]
        print(json.dumps(out))
    except Exception:
        print("[]")


if __name__ == "__main__":
    main()
