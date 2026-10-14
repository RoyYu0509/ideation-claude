#!/usr/bin/env python3
"""classify_crash.py — mechanical crash-cause classifier + transient-event ledger (capture hygiene).

The regex twin of plugins/experiment-lab-ar/spec/failure/transient.md (the prose SSOT) — signature changes
move together there and here. Cause closed-set: env_transient | oom | code | unknown. OOM is deliberately
its OWN cause (awaiting adjudication by one identical re-run — contention vs capacity wall), never folded
into env_transient by signature alone.

Subcommands (stdlib only, deterministic):
  classify --exit-code <str> --tail-file <file>
      → prints "CAUSE <enum>" + "PATTERN <name>". Pure single classification (unit-testable).
  annotate --marker <.crash-*.json>
      → reads the auto-research-crash@1 marker, adds `cause` to every crashes[] entry (idempotent), writes
        it back, prints "CAUSES <comma-joined unique causes>". Keeps L0 thin: the orchestrator never
        classifies in-context, and the raw traceback never crosses a shell string.
  scan --ws <workspace> [--events <run-events.jsonl>] --out <transient-events.json>
      → the transient-event ledger for /learn: every crash-marker entry + FAILURES.md crash line (tagged
        [cause:*] or legacy-untagged but signature-matched) with its RESOLVED pairing, plus detached_crash /
        detached_anomaly events. Detector discipline: ALWAYS exit 0; prints a <=10-line SUMMARY.
"""
import argparse, glob, json, os, re, sys

CAUSE_PATTERNS = [
    # (cause, pattern-name, regex) — first match wins; checked against exit_code string THEN stdout tail
    ("env_transient", "pid-dead-no-exitcode", re.compile(r"killed \(PID died mid-run, no exitcode\)", re.I)),
    ("env_transient", "api-overload",         re.compile(r"\b(429|529)\b|overloaded|rate.?limit", re.I)),
    ("env_transient", "network",              re.compile(r"connection (refused|reset)|timed?.?out|temporarily unavailable", re.I)),
    ("env_transient", "disk-full",            re.compile(r"no space left on device", re.I)),
    ("oom",           "oom",                  re.compile(r"CUDA out of memory|MemoryError|OOMKilled|oom.?kill", re.I)),
    ("code",          "traceback",            re.compile(r"Traceback \(most recent call last\)|AssertionError|SyntaxError|NameError|AttributeError|KeyError|IndexError", re.I)),
]

def classify(exit_code, tail):
    for text in (str(exit_code or ""), str(tail or "")):
        for cause, name, rx in CAUSE_PATTERNS:
            if rx.search(text):
                return cause, name
    return "unknown", "no-signature"

def cmd_classify(a):
    tail = ""
    if a.tail_file and os.path.exists(a.tail_file):
        tail = open(a.tail_file, errors="ignore").read()
    cause, name = classify(a.exit_code, tail)
    print(f"CAUSE {cause}"); print(f"PATTERN {name}")

def cmd_annotate(a):
    with open(a.marker, encoding="utf-8") as f:
        d = json.load(f)
    causes = []
    for c in d.get("crashes") or []:
        if not c.get("cause"):
            c["cause"], c["cause_pattern"] = classify(c.get("exit_code"), c.get("stdout_tail"))
        causes.append(c["cause"])
    tmp = a.marker + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    os.replace(tmp, a.marker)
    seen = []
    for c in causes:
        if c not in seen:
            seen.append(c)
    print("CAUSES " + (",".join(seen) or "unknown"))

TAG_RX = re.compile(r"\[cause:([a-z_]+)\]")

def cmd_scan(a):
    events = []
    # (1) crash markers — the full-evidence records
    for marker in sorted(glob.glob(os.path.join(a.ws, ".crash-*.json"))):
        try:
            d = json.load(open(marker, encoding="utf-8"))
        except Exception:
            continue
        for c in d.get("crashes") or []:
            cause = c.get("cause") or classify(c.get("exit_code"), c.get("stdout_tail"))[0]
            events.append({"source": "crash_marker", "marker": os.path.basename(marker),
                           "milestone": d.get("milestone"), "ledger_id": c.get("ledger_id"),
                           "cause": cause, "resolved": False})
    # (2) FAILURES.md crash lines (+ RESOLVED pairing by milestone token; legacy untagged lines re-classified)
    failures_p = os.path.join(a.ws, "FAILURES.md")
    if os.path.exists(failures_p):
        lines = open(failures_p, errors="ignore").read().splitlines()
        resolved_ms = set()
        for ln in lines:
            m = re.search(r"\]\s*([^:]+):\s*RESOLVED", ln)
            if m:
                resolved_ms.add(m.group(1).strip())
        for ln in lines:
            if "RESOLVED" in ln or "crash" not in ln.lower():
                continue
            m = re.search(r"\]\s*([^:]+):", ln)
            ms = m.group(1).strip() if m else None
            tag = TAG_RX.search(ln)
            cause = tag.group(1) if tag else classify("", ln)[0]
            events.append({"source": "failures_line", "milestone": ms, "cause": cause,
                           "resolved": bool(ms and ms in resolved_ms), "line": ln[:200]})
    # (3) run-events side-channel (optional)
    if a.events and os.path.exists(a.events):
        for ln in open(a.events, errors="ignore"):
            try:
                ev = json.loads(ln)
            except Exception:
                continue
            if ev.get("event") in ("detached_crash", "detached_anomaly"):
                events.append({"source": "run_event", "event": ev.get("event"),
                               "cause": None, "resolved": None,
                               "detail": {k: v for k, v in ev.items() if k not in ("event",)}})
    out = {"schema": "auto-research-transient-events@1", "ws": a.ws, "events": events}
    if a.out:
        tmp = a.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        os.replace(tmp, a.out)
    transient = [e for e in events if e.get("cause") == "env_transient"]
    oom = [e for e in events if e.get("cause") == "oom"]
    print(f"SUMMARY transient-events: {len(transient)} env_transient, {len(oom)} oom(unadjudicated), "
          f"{len(events)} total records" + (f" -> {a.out}" if a.out else ""))
    for e in (transient + oom)[:9]:
        where = e.get("milestone") or e.get("ledger_id") or e.get("source")
        print(f"SUMMARY   {e['cause']}  {where}  resolved={e.get('resolved')}")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify"); c.add_argument("--exit-code", default=""); c.add_argument("--tail-file", default=None); c.set_defaults(fn=cmd_classify)
    an = sub.add_parser("annotate"); an.add_argument("--marker", required=True); an.set_defaults(fn=cmd_annotate)
    s = sub.add_parser("scan"); s.add_argument("--ws", required=True); s.add_argument("--events", default=None); s.add_argument("--out", default=None); s.set_defaults(fn=cmd_scan)
    a = p.parse_args()
    try:
        a.fn(a)
    except Exception as e:
        # detector discipline for scan; classify/annotate fail loud (they gate a write)
        if a.cmd == "scan":
            print(f"SUMMARY scan degraded (non-fatal): {e}")
            sys.exit(0)
        print(f"ERROR classify_crash {a.cmd}: {e}"); sys.exit(2)

if __name__ == "__main__":
    main()
