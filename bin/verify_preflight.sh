#!/usr/bin/env bash
# bin/verify_preflight.sh — B4-25 MECHANICAL PREFLIGHT for the independent verifier (VERIFY-PROTOCOL.md).
# The terminal verify_final is a single no-spawn context asked to deliver ~12 structured obligations at once;
# breadth crowds out DEPTH on the one lethal clue. This script SINKS the five PURELY-MECHANICAL existence /
# sync / provenance facts out of that context so the verifier READS them (never re-derives) and spends its
# reasoning on the checks that need judgement. It is a PURE SENSOR: it writes facts to <ws>/.verify-preflight.json
# and — apart from a usage/script error (exit 2, fail loud) — NEVER exits non-zero. It renders NO verdict; the
# verifier reads the facts and judges. Mechanical logic lives HERE (a NEW file), never in bin/verify_panel.sh.
#
# The five checks (and ONLY these five; V1/V2/V3/V5/V8/V9/V10 judgement stays in the md):
#   V4-gate4a-verdict-presence  — is a Gate-4a / reproduce-first verdict RECORDED in RESEARCH_LOG.md?   [both scopes]
#   claim-correspondence-verdict-presence — does every EXPERIMENTS/*/result.md record its (c) verdict    [both scopes]
#                                 (structural + behavioral halves, experiment-protocol Phase 5)? The
#                                 PRESENCE half of the split gate; V8 (vi) re-derives the correctness half.
#   V6-number-sync-candidates   — target decimals with no match in result.json/CLAIMS.md/FAILURES.md/     [both scopes]
#                                 AUDITED-VALUES.json; target = paper .tex, or FINDINGS-DOSSIER.md when
#                                 no paper exists (in-loop). (CANDIDATES only — the verifier judges
#                                 materiality; never belts)
#   V7-figure-plot-script-trace — every \includegraphics file exists + a plot script exists under code/   [science]
#   cite-bib-fabrication        — every \cite key has a real .bib entry (a fabricated \cite is a fact)     [science]
# Each check: { check, status: PASS|FAIL|NA, belt: <bool>, evidence }. A check outside the scope, or a figure
# check when require_figures=false / no figures, is NA. `belt_fail` = any belt-eligible check FAILed — the L0
# fail-closed belt overrides a verifier PASS on it (mechanical fact wins). V6 is belt:false (advisory candidates).
#
# Usage:  bin/verify_preflight.sh <workspace> <scope:science|focused>
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONFIG="${PLUGIN_ROOT}/config/config.yaml"

WS="${1:-}"; SCOPE="${2:-}"
[ -n "$WS" ]                                   || { echo "ERROR verify_preflight: need <workspace> argument"; exit 2; }
[ -d "$WS" ]                                   || { echo "ERROR verify_preflight: workspace not found: $WS"; exit 2; }
case "$SCOPE" in science|focused) : ;; *) echo "ERROR verify_preflight: need <scope> = science|focused (got '$SCOPE')"; exit 2 ;; esac

WS="$WS" SCOPE="$SCOPE" CONFIG="$CONFIG" python3 - <<'PY'
import os, sys, json, glob, re

ws = os.environ["WS"]; scope = os.environ["SCOPE"]; cfg_path = os.environ["CONFIG"]
def fail(m): print("ERROR verify_preflight: " + m); sys.exit(2)

# require_figures (config drafting.require_figures) — decides whether the figure check is live or NA.
require_figures = True
try:
    import yaml
    cfg = yaml.safe_load(open(cfg_path)) or {}
    rf = (cfg.get("drafting") or {}).get("require_figures")
    require_figures = True if rf is None else bool(rf)
except Exception:
    require_figures = True   # sensor stays permissive; the verifier's V7 arm is the real gate

def read(p):
    try:
        return open(p, errors="ignore").read()
    except Exception:
        return ""

paper_dir = os.path.join(ws, "paper")
tex_files = glob.glob(os.path.join(paper_dir, "**", "*.tex"), recursive=True)
bib_files = glob.glob(os.path.join(paper_dir, "**", "*.bib"), recursive=True)
tex_all = "\n".join(read(f) for f in tex_files)

checks = []
def add(check, status, belt, evidence):
    checks.append({"check": check, "status": status, "belt": belt, "evidence": evidence})

# ── V4 — Gate-4a / reproduce-first recorded verdict PRESENCE in RESEARCH_LOG.md (both scopes) ──────────
log_p = os.path.join(ws, "RESEARCH_LOG.md")
log_txt = read(log_p)
if not log_txt.strip():
    add("V4-gate4a-verdict-presence", "NA", True,
        "RESEARCH_LOG.md absent/empty — too early to judge Gate-4a presence")
else:
    # a recorded verdict = a Gate-4a / reproduce-first / Phase-4 anchor near a passed | not_applicable token
    anchor = r'(gate[\s\-]*4a|reproduce[\s\-]*first|phase[\s\-]*4)'
    verdict = r'(pass(?:ed)?|not[\s_\-]*applicable|n/?a\b)'
    hit = re.search(anchor + r'.{0,120}' + verdict, log_txt, re.I | re.S) \
       or re.search(verdict + r'.{0,120}' + anchor, log_txt, re.I | re.S)
    if hit:
        add("V4-gate4a-verdict-presence", "PASS", True,
            "recorded Gate-4a/reproduce-first verdict found in RESEARCH_LOG.md")
    else:
        add("V4-gate4a-verdict-presence", "FAIL", True,
            "no Gate-4a/reproduce-first recorded verdict (passed|not_applicable) in RESEARCH_LOG.md")

# ── claim-correspondence (c) verdict PRESENCE in every EXPERIMENTS/*/result.md (both scopes) ──────────
# The mechanical PRESENCE half of the split claim-correspondence gate (GATE-TAXONOMY §4): the producer's
# self-recorded verdict must EXIST with both halves; whether it is CORRECT is V8 (vi)'s judgement.
result_mds = sorted(glob.glob(os.path.join(ws, "EXPERIMENTS", "*", "result.md")))
if not result_mds:
    add("claim-correspondence-verdict-presence", "NA", True,
        "no EXPERIMENTS/*/result.md on disk yet — nothing to check")
else:
    cc_anchor = re.compile(r'claim[\s\-_]*correspondence', re.I)
    deferral_anchor = re.compile(r'THIS IS A DEFERRAL RECORD,\s*NOT A RUN', re.I)
    cc_missing = []
    for p in result_mds:
        seg = os.path.basename(os.path.dirname(p))
        body = read(p)
        if deferral_anchor.search(body):
            # a segment self-declared "THIS IS A DEFERRAL RECORD, NOT A RUN" (experiment-protocol §2.3) never
            # executed — no manifest, no verdict, nothing to have a claim-correspondence verdict ABOUT. Exempt,
            # same as the "no result.md yet" NA case above; do not flag a deliberate non-run as a missing verdict.
            continue
        if not cc_anchor.search(body):
            cc_missing.append(seg + ": no claim-correspondence verdict recorded")
            continue
        low = body.lower()
        halves = [w for w in ("structural", "behavioral") if w not in low]
        if halves:
            cc_missing.append(seg + ": claim-correspondence verdict missing its " + "+".join(halves) + " half")
    if cc_missing:
        add("claim-correspondence-verdict-presence", "FAIL", True,
            {"note": "result.md missing the claim-correspondence (c) verdict (structural + behavioral halves, experiment-protocol Phase 5)",
             "missing": cc_missing[:20]})
    else:
        add("claim-correspondence-verdict-presence", "PASS", True,
            "every EXPERIMENTS/*/result.md records a claim-correspondence verdict with structural + behavioral halves")

# ── V6 — number-sync CANDIDATES: target decimals absent from the source artifacts (both scopes) ───────
# Target = paper .tex when it exists; in the loop (writing-redesign: no paper until post-freeze) the
# number-bearing artifact is FINDINGS-DOSSIER.md — scan THAT so the loop is never sensor-blind on sync.
NUM = re.compile(r'(?<![\w.])\d+\.\d+(?:[eE][-+]?\d+)?')
def nums(txt):
    out = set()
    for m in NUM.findall(txt or ""):
        try:
            out.add(float(m))
        except Exception:
            pass
    return out
src_txt = ""
for p in glob.glob(os.path.join(ws, "code", "**", "result.json"), recursive=True) \
       + glob.glob(os.path.join(ws, "EXPERIMENTS", "**", "result.json"), recursive=True) \
       + [os.path.join(ws, "CLAIMS.md"), os.path.join(ws, "FAILURES.md"),
          os.path.join(ws, "AUDITED-VALUES.json")]:
    src_txt += "\n" + read(p)
src_nums = nums(src_txt)
dossier_txt = read(os.path.join(ws, "FINDINGS-DOSSIER.md"))
if tex_all.strip():
    target_txt, target_name = tex_all, "paper"
else:
    target_txt, target_name = dossier_txt, "FINDINGS-DOSSIER.md"
target_nums = nums(target_txt)
def matched(x):
    return any(abs(x - s) <= 1e-9 * max(1.0, abs(s)) for s in src_nums)
candidates = sorted({("%g" % x) for x in target_nums if not matched(x)})
if not target_txt.strip():
    add("V6-number-sync-candidates", "NA", False, "no paper .tex and no FINDINGS-DOSSIER.md to scan")
elif candidates:
    add("V6-number-sync-candidates", "FAIL", False,
        {"note": "ADVISORY candidates — %s decimals with no source match; verifier judges materiality (rounding/format vs real drift)" % target_name,
         "target": target_name, "candidates": candidates[:20], "total": len(candidates)})
else:
    add("V6-number-sync-candidates", "PASS", False,
        "every %s decimal matches a source artifact number" % target_name)

# ── V7 — figure→plot-script trace (SCIENCE only; NA in focused / when require_figures=false / no figs) ─
if scope != "science":
    add("V7-figure-plot-script-trace", "NA", True, "figure provenance is a SCIENCE-scope check (skipped in focused)")
elif not require_figures:
    add("V7-figure-plot-script-trace", "NA", True, "require_figures=false — a figureless paper is legal (verifier V7 decides)")
else:
    inc = re.findall(r'\\includegraphics(?:\[[^\]]*\])?\s*\{([^}]*)\}', tex_all)
    if not inc:
        add("V7-figure-plot-script-trace", "NA", True, "no \\includegraphics in the paper (verifier V7 arm judges the require_figures floor)")
    else:
        # every included figure file must exist somewhere under paper/ (latex often omits the extension)
        paper_files = glob.glob(os.path.join(paper_dir, "**", "*"), recursive=True)
        basenames = set(os.path.basename(p) for p in paper_files)
        stems = set(os.path.splitext(os.path.basename(p))[0] for p in paper_files)
        missing = [t for t in inc
                   if os.path.basename(t) not in basenames
                   and os.path.splitext(os.path.basename(t))[0] not in stems]
        # a plot script = a .py under code/ that actually plots (savefig / matplotlib)
        plot_script = False
        for p in glob.glob(os.path.join(ws, "code", "**", "*.py"), recursive=True):
            body = read(p)
            if "savefig" in body or "matplotlib" in body or "plt." in body:
                plot_script = True
                break
        if missing:
            add("V7-figure-plot-script-trace", "FAIL", True,
                {"note": "included figure file(s) not found on disk under paper/", "missing": missing[:20]})
        elif not plot_script:
            add("V7-figure-plot-script-trace", "FAIL", True,
                "figures are \\includegraphics'd but NO plot script (savefig/matplotlib) exists under code/ — untraced provenance")
        else:
            add("V7-figure-plot-script-trace", "PASS", True,
                "every included figure file exists and a plot script is present under code/")

# ── \cite → .bib fabrication (SCIENCE only; NA in focused) ─────────────────────────────────────────────
if scope != "science":
    add("cite-bib-fabrication", "NA", True, "citation checks are SCIENCE-scope (skipped in focused)")
else:
    cite_keys = set()
    for grp in re.findall(r'\\[a-zA-Z]*cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}', tex_all):
        for k in grp.split(","):
            k = k.strip()
            if k:
                cite_keys.add(k)
    bib_keys = set()
    for f in bib_files:
        for k in re.findall(r'@\w+\s*\{\s*([^,\s]+)\s*,', read(f)):
            bib_keys.add(k.strip())
    if not cite_keys:
        add("cite-bib-fabrication", "NA", True, "no \\cite keys in the paper to check")
    else:
        fabricated = sorted(cite_keys - bib_keys)
        if fabricated:
            add("cite-bib-fabrication", "FAIL", True,
                {"note": "\\cite key(s) with no matching .bib entry (fabricated citation)", "fabricated": fabricated[:20]})
        else:
            add("cite-bib-fabrication", "PASS", True, "every \\cite key resolves to a real .bib entry")

belt_failed = [c["check"] for c in checks if c["belt"] and c["status"] == "FAIL"]
out = {
    "scope": scope,
    "require_figures": require_figures,
    "checks": checks,
    "belt_fail": bool(belt_failed),
    "belt_failed_checks": belt_failed,
}
out_path = os.path.join(ws, ".verify-preflight.json")
with open(out_path, "w") as fh:
    json.dump(out, fh, indent=2)
print("OK verify_preflight: scope=%s -> %s (%d checks, belt_fail=%s)"
      % (scope, out_path, len(checks), bool(belt_failed)))
PY
