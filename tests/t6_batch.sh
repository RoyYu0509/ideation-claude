#!/usr/bin/env bash
# T6 — single-idea selection + run-end mechanics. Mirrors the [[MECH]] logic the L0 session reproduces
# from spec/research.js after the batch/queue was removed: GATE-1 ingest (applyPickedIdea — take the ONE
# picked idea = first Keep in presentation order, ignore the rest; venue validation; no-keep ends the
# run), finishRun (seal → record final status → stage='done', NO next item), and batchGroundClean (seal
# BOTH .polish/ locations, quiesce gate, kill a live PID a pidfile still tracks). Pure shell + python3,
# t4-style, no live session.
# Run: bash tests/t6_batch.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT/config/config.yaml"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
chk() { if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

export TMP CONFIG
OUT=$(python3 - <<'PY'
import os, json, re, subprocess, yaml

TMP, CONFIG = os.environ["TMP"], os.environ["CONFIG"]
cfg = yaml.safe_load(open(CONFIG))
def need(d, *path):
    node = d
    for seg in path:
        assert isinstance(node, dict) and seg in node, "<MISSING KEY: %s>" % ".".join(path)
        node = node[seg]
    return node
# SSOT sanity: the batch block is GONE (single-idea model). No continue_on_failure either.
assert "batch" not in cfg, "the batch config block must be removed (single-idea model)"
assert "continue_on_failure" not in cfg, "continue_on_failure must not exist"

SF = os.path.join(TMP, "state", "pipeline-state.json")
os.makedirs(os.path.dirname(SF), exist_ok=True)
def persist(s): json.dump(s, open(SF, "w"), indent=2)
def load():     return json.load(open(SF))

# ── stub 3 refined seed files (one file per idea — the flat F2 model) ───────────────────────────
seeds = []
os.makedirs(os.path.join(TMP, "refined"), exist_ok=True)
for n, title in enumerate(["ACE Collision in Moment Space", "Metriplectic Closure Solver",
                           "Body-Order Ladder for Dense Gas"], 1):
    f = os.path.join(TMP, "refined", "2506.0000%d-idea1.md" % n)
    open(f, "w").write("# %s\nHYPOTHESIS: H%d\n" % (title, n))
    seeds.append({"id": "2506.0000%d-idea1" % n, "title": title, "file": f})

def slugify(t): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", t.lower())).strip("-")

PREPARED_VENUES = ["Journal-of-Computational-Physics/scientific-machine-learning",
                   "Nature-Computational-Science/scientific-machine-learning"]
DEFAULT_VENUE = PREPARED_VENUES[0]

# ── [[MECH]] mirror of applyPickedIdea: take the FIRST Keep, ignore the rest; no-keep ends the run ─
def apply_picked_idea(state, keeps, default_venue, per_idea=None):
    """keeps = list of idea ids answered Keep, in presentation order. Returns the action taken:
       'venue'  -> re-presented the venue gate (bad default venue), nothing applied;
       'none'   -> owner kept nothing -> stage='done';
       'picked' -> first Keep researched (flat fields set, stage='setup_workspace')."""
    if default_venue not in PREPARED_VENUES:               # a run never starts on an unprepared venue
        return "venue"
    kept = [s for s in seeds if s["id"] in keeps]          # presentation order (seeds order)
    if not kept:
        state["final_status"] = "abandoned"; state["exit_reason"] = "no_idea_selected"
        state["stage"] = "done"; persist(state); return "none"
    s = kept[0]                                            # the ONE idea; the rest are IGNORED
    ov = (per_idea or {}).get(s["id"], {})
    note = ov.get("notes")
    m = re.search(r"venue:\s*([^\s,;]+)", note) if note else None
    venue = m.group(1) if (m and m.group(1) in PREPARED_VENUES) else default_venue
    state["paper_slug"] = slugify(s["title"]); state["workspace"] = "runs/" + state["paper_slug"]
    state["venue"] = venue; state["picked_seed_file"] = s["file"]; state["notes"] = note
    state["loop_round"] = 0; state["milestone"] = None; state["detached"] = []
    state["stage"] = "setup_workspace"; persist(state); return "picked"

def ground_clean(state, polish_dirs):
    """batchGroundClean: quiesce detached, then JOIN/KILL any live PID a pidfile still tracks
    (state.detached can miss one if a 529 ate the envelope), then clear pidfile + manifest in
    EVERY .polish/ location (V-A)."""
    assert not state.get("detached"), "detached jobs must be quiesced before the seal"
    killed = []
    for d in polish_dirs:
        pf = os.path.join(d, ".bg-pids")
        if os.path.exists(pf):
            for line in open(pf):
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    try:
                        os.kill(pid, 0)                 # alive? -> runaway: kill, never rm blind
                        os.kill(pid, 15); killed.append(pid)
                    except (ProcessLookupError, PermissionError):
                        pass
            os.remove(pf)
        mf = os.path.join(d, "fidelity-manifest.json")
        if os.path.exists(mf): os.remove(mf)
    return killed

def finish_run(state, final_status, reason, polish_dirs=()):
    ground_clean(state, polish_dirs)                    # seal: quiesce + clear .polish
    state["final_status"] = final_status; state["exit_reason"] = reason
    state["stage"] = "done"; persist(state)             # one run pursues ONE idea — no next item

R = {}

# ── pick.1 first Keep is researched; OTHER Keeps are ignored ─────────────────────────────────────
state = {"stage": "seed_gate", "detached": [], "history": []}; persist(state)
act = apply_picked_idea(state, [seeds[1]["id"], seeds[2]["id"]], DEFAULT_VENUE)   # Keep #2 and #3
s = load()
R["first_keep_wins"] = (act == "picked"
                        and s["paper_slug"] == slugify(seeds[1]["title"])         # #2 = first in order kept
                        and s["venue"] == DEFAULT_VENUE and s["loop_round"] == 0
                        and s["milestone"] is None and s["stage"] == "setup_workspace"
                        and s.get("picked_seed_file") == seeds[1]["file"])

# ── pick.2 no Keep -> the run ends (re-run /auto-research to choose again) ───────────────────────
state = {"stage": "seed_gate", "detached": [], "history": []}; persist(state)
act = apply_picked_idea(state, [], DEFAULT_VENUE)
s = load()
R["no_keep_ends_run"] = (act == "none" and s["stage"] == "done"
                         and s["final_status"] == "abandoned" and s["exit_reason"] == "no_idea_selected"
                         and s.get("paper_slug") is None)

# ── pick.3 bad default venue -> re-present the venue gate, nothing applied ───────────────────────
state = {"stage": "seed_gate", "detached": [], "history": []}; persist(state)
act = apply_picked_idea(state, [seeds[0]["id"]], "Made-Up-Venue/none")
R["bad_venue_represents"] = (act == "venue" and load().get("paper_slug") is None
                             and load()["stage"] == "seed_gate")

# ── pick.4 per-idea "venue:" note overrides the default; the note is captured ────────────────────
state = {"stage": "seed_gate", "detached": [], "history": []}; persist(state)
note = "venue: %s ; frame around H-theorem guarantees" % PREPARED_VENUES[1]
act = apply_picked_idea(state, [seeds[0]["id"]], DEFAULT_VENUE, per_idea={seeds[0]["id"]: {"notes": note}})
s = load()
R["venue_override_and_note"] = (act == "picked" and s["venue"] == PREPARED_VENUES[1]
                                and s["notes"] == note)

# ── pick.5 the note carries into the rendered HANDOFF goal (no note -> no clause) ────────────────
def seed_to_handoff_goal(picked_seed_file, notes):     # mirrors seedToHandoffGoal's notes clause
    goal = "Read the picked /research seed at %s ..." % picked_seed_file
    if notes:
        goal += ("\nAUTHOR'S ANGLE / NOTES: %s — fold into framing/emphasis; never override the"
                 " seed's science or kill criteria.") % notes
    return goal
g = seed_to_handoff_goal(s["picked_seed_file"], s["notes"])
R["note_in_handoff_goal"] = "frame around H-theorem guarantees" in g and "never override" in g
R["no_note_no_clause"] = "AUTHOR'S ANGLE" not in seed_to_handoff_goal("f", None)

# ── finish.1 ship -> seal + stage='done' (no next item) ─────────────────────────────────────────
state = {"stage": "ship", "paper_slug": "slug-a", "detached": [], "history": []}; persist(state)
finish_run(state, "shipped", "clean_exit")
s = load()
R["ship_ends_run"] = (s["stage"] == "done" and s["final_status"] == "shipped"
                      and s["exit_reason"] == "clean_exit")

# ── finish.2 abandon -> stage='done' (re-run /auto-research to try another idea) ─────────────────
state = {"stage": "loop", "paper_slug": "slug-a", "detached": [], "history": []}; persist(state)
finish_run(state, "abandoned", "owner_abandoned_at_hardstop")
s = load()
R["abandon_ends_run"] = (s["stage"] == "done" and s["final_status"] == "abandoned")

# ── seal.1 batchGroundClean seals BOTH .polish/ locations during finishRun ──────────────────────
root_polish = os.path.join(TMP, ".polish"); run_polish = os.path.join(TMP, "runs", "slug-b", ".polish")
for d in (root_polish, run_polish):
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, ".bg-pids"), "w").write("12345\n")
    open(os.path.join(d, "fidelity-manifest.json"), "w").write("{}")
state = {"stage": "ship", "paper_slug": "slug-b", "detached": [], "history": []}; persist(state)
finish_run(state, "shipped", "clean_exit", polish_dirs=(root_polish, run_polish))
R["seal_both_polish"] = not any(os.path.exists(os.path.join(d, f))
                                for d in (root_polish, run_polish)
                                for f in (".bg-pids", "fidelity-manifest.json"))

# ── seal.2 a live detached entry must BLOCK the seal (quiesce gate) ──────────────────────────────
state = {"detached": [{"pidfile": "x"}]}
try:
    ground_clean(state, ()); R["seal_requires_quiesce"] = False
except AssertionError:
    R["seal_requires_quiesce"] = True

# ── seal.3 a LIVE PID still in a pidfile (state.detached missed it — a 529 ate the envelope) is
#    KILLED before the pidfile is cleared — never rm a live PID blind ─────────────────────────────
proc = subprocess.Popen(["sleep", "300"])
d = os.path.join(TMP, ".polish-live"); os.makedirs(d, exist_ok=True)
open(os.path.join(d, ".bg-pids"), "w").write("%d\n" % proc.pid)
state = {"detached": []}
killed = ground_clean(state, (d,))
try:
    proc.wait(timeout=5); reaped = True
except subprocess.TimeoutExpired:
    proc.kill(); reaped = False
R["seal_kills_live_pid"] = (proc.pid in killed and reaped
                            and not os.path.exists(os.path.join(d, ".bg-pids")))

print("RESULT " + json.dumps(R))
PY
)
echo "$OUT" | sed -n '$p' > "$TMP/result.json"

for key in first_keep_wins no_keep_ends_run bad_venue_represents venue_override_and_note \
           note_in_handoff_goal no_note_no_clause ship_ends_run abandon_ends_run \
           seal_both_polish seal_requires_quiesce seal_kills_live_pid; do
  chk "$key" "grep -q '\"$key\": true' '$TMP/result.json'"
done
echo "----"; echo "t6_batch: $pass passed, $fail failed"; [ "$fail" = 0 ]
