---
name: experiment-engineering
description: Hardware-aware experiment engineering — probe the real machine and size the EXECUTION to it (never pre-shrink the SCIENCE); OOM-precheck, maximize CPU/GPU use, lock seeds. Loaded by name by the B1 experiment_worker.
user-invocable: false
---

# experiment-engineering — probe the real machine, size to it, never scale down the science

You are the `experiment_worker` (auto-research B1): you write and run the REAL experiment code on THIS
machine via local Bash. Two failure modes this skill removes: (1) running blind to the hardware and only
discovering an OOM or a 10× slowdown hours into a full-scale run; (2) confusing a cheap **engineering
probe** with a forbidden **scaled-down science run**. Read section 2 before you touch the no-scaled-down rule.

## 1. Probe THIS machine — first thing, every session

**REMOTE MODE — read this before the injected block.** If `AR_REMOTE_HOST` is set, the science does NOT run
here: it runs on a remote Slurm cluster through `bin/remote_exec.sh`, and every number injected below
describes the WRONG machine (this is the orchestrating laptop, not the executor). Probe the real executor
instead — reading Slurm's node CONFIGURATION costs nothing and needs no queue wait:

```bash
H="$AR_REMOTE_HOST"; P="${AR_SLURM_PARTITION:-gpu}"
ssh -n "$H" "sinfo -p $P -o '%N | gres=%G | cpus=%c | mem_mb=%m | timelimit=%l'"   # 执行机真实规格
ssh -n "$H" "sinfo -p $P -o '%F'; squeue -p $P -t PENDING -h | wc -l"              # 空闲 A/I/O/T + 排队深度
```

Size the EXECUTION to THOSE numbers. Everything else in this skill is unchanged, with ONE substitution: a
science run's `--cmd` becomes `bin/remote_exec.sh <segment> <remote-dir> '<command>' '<products>'`, which
blocks in the foreground until the remote job leaves the queue — so `run-detach` + the re-wake hook work
exactly as documented in `experiment-protocol.md` §4. **Queue wait is free**: it burns no tokens, no
compute, and is not billed. Never shrink a run to dodge the queue, and never fall back to running the
science on this laptop because the queue looks long — a laptop-sized run of a cluster-sized contract is
the forbidden scaled-down run.

These are this machine's real numbers, injected when the skill loads:

- logical cores — !`echo "$(sysctl -n hw.ncpu 2>/dev/null || nproc)"`
- RAM (GB) — !`echo "$(( $(sysctl -n hw.memsize 2>/dev/null || awk '/MemTotal/{print $2*1024}' /proc/meminfo 2>/dev/null) / 1073741824 ))"`
- GPU — !`nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || system_profiler SPDisplaysDataType 2>/dev/null | awk -F: '/Chipset Model/{print $2}' | head -1 || echo none`
- torch compute device on THIS machine (what tensors should target — auto-detected, NOT assumed) — !`python3 -c "import torch; print('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')" 2>/dev/null || echo "torch not importable"`

If that block came back blank (the injection did not run in this context), immediately run the same probe
yourself with Bash — never size a run blind:

```bash
echo "cores=$(sysctl -n hw.ncpu 2>/dev/null || nproc)  ram_gb=$(( $(sysctl -n hw.memsize 2>/dev/null || awk '/MemTotal/{print $2*1024}' /proc/meminfo) / 1073741824 ))"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null \
  || system_profiler SPDisplaysDataType 2>/dev/null | awk -F: '/Chipset Model/{print $2}'
python3 - <<'PY' 2>/dev/null
import os
try:
    import torch
    print("torch", torch.__version__, "cuda", torch.cuda.is_available(),
          "mps", getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
    for i in range(torch.cuda.device_count() if torch.cuda.is_available() else 0):
        p = torch.cuda.get_device_properties(i); print(f"  gpu{i} {p.name} {p.total_memory/1e9:.1f}GB")
except ImportError:
    print("no torch")
print("os.cpu_count", os.cpu_count())
PY
```

These numbers size the EXECUTION only (device, parallel width, memory partition) — NEVER the SCIENCE scale, which is hardware-blind and comes from the locked SCALE-CONTRACT (§3). On Apple Silicon (no CUDA) the GPU is reachable only
via the `mps` backend, and its memory is **unified with system RAM** — treat it as shared, not as separate
VRAM.

## 2. Probe vs scaled-down — NOT the same thing (read before section 3)

The rule **"no smoke / no scaled-down science run"** stands: never take a run with shrunk
epochs/data/problem-size and read a **scientific conclusion** off it — a too-short PINN fakes "no
heteroscedasticity", a 1-seed run fakes "no effect", and that false conclusion is exactly what the pipeline
exists to prevent.

But that rule governs the **source of a scientific claim**, not the **measurement of engineering
capacity**. An *engineering probe* produces no scientific claim: it runs the minimal input (1 batch, 1 step,
the shortest sequence) only to measure — does it import, how much memory one step costs, the throughput,
whether full scale will OOM. Its output is "what batch size this machine allows",
nothing else.

The test, in one line: **a probe's output only CONFIGURES the full-scale run — it never replaces it, never
enters `RESEARCH_LOG.md` as a result, never backs a K-criterion, never reaches the paper.** Inside that
boundary, probe-then-scale-up is *required* engineering discipline. Cross it — quote a probe's small-scale
number as a finding — and it is the forbidden scaled-down run.

## 3. OOM is handled REACTIVELY — author full, let it fail, then partition (never down-scale)

Do NOT pre-shrink a run to fit this machine. The SCIENCE scale (under_test + the full control grid) comes
from the locked SCALE-CONTRACT and is HARDWARE-BLIND: author every run at the contract's full scale whatever
this machine's RAM/VRAM. Then let the hardware tell you the truth — EVERY full-scale run fires DETACHED
(`exp_ledger.py run-detach`) and is re-waked (no short/long judgment, never run or polled in the foreground;
the wave loop owns this). Wrap the real run so an OOM fails LOUDLY (the auditor re-reads this log):

```python
try:
    train_full_scale(cfg)                    # cfg is READ FROM the SCALE-CONTRACT — full scale, hardware-blind
except (torch.cuda.OutOfMemoryError, MemoryError):
    torch.cuda.empty_cache()
    raise SystemExit("OOM at full scale -> REMEDIATION (experiment-protocol.md): re-express the SAME "
                     "full-scale science as memory-bounded SERIAL scripts. NEVER lower a science value.")
```

On that OOM, follow the REMEDIATION protocol: re-express the full-scale science as MULTIPLE memory-bounded
scripts run SERIALLY — partition the seed/control grid across separate processes, tile a large domain, or use
gradient checkpointing / accumulation / mixed precision WITHIN a script. Each choice keeps the FULL science
(every seed, the whole grid) and shrinks only the per-process footprint; the L0 scale audit checks the
AGGREGATE meets the contract, so a "partition" that secretly drops seeds/sizes is caught as a down-scale.
Down-scaling the science to dodge OOM is FORBIDDEN; surface an S3 resource wall ONLY when the single smallest
irreducible unit cannot fit. Tee peak memory into the run's stdout log next to the result. For CPU/RAM jobs
the analogue is `psutil.Process().memory_info().rss` against the probed RAM.

## 4. Use the hardware — don't leave the machine idle

Default to saturating what you probed:

- **Device once** — author for the device the §1 probe reported on THIS machine; `.to(device)` model +
  batch a single time, never ping-pong tensors in a loop.
  `device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")`.
  If a library friction shows up on that device (e.g. a tensor that needs `.cpu()` before `.numpy()`, an
  unimplemented op), fix that one line — never force the whole run back to CPU to dodge it.
- **Standard single-GPU throughput levers** — vectorize away per-sample Python `for` loops; `DataLoader`
  `num_workers`/`pin_memory`; mixed-precision `autocast`/`GradScaler`; `torch.compile` — apply as the op set
  allows. Current-API recipes + pitfalls: `reference/pytorch-single-gpu.md` (§1 精度加速 / §3 torch.compile / §5 数据管线).
- **Multi-GPU** — only if the probe shows >1 GPU (this backend is a single local machine); then DDP.
- **Pure-CPU science — parallelize at ONE level only.** Two axes MULTIPLY and must not stack: BLAS threads
  (`OMP_NUM_THREADS`/`MKL_NUM_THREADS`) parallelize NumPy/SciPy WITHIN one run; a process pool parallelizes
  ACROSS independent runs. `pool_workers × blas_threads_per_worker` ≈ probed cores, else you oversubscribe
  N× and run SLOWER than serial.
  - **Many independent runs** (parameter grid, multi-seed, ablations — embarrassingly parallel): the common
    case and the biggest lever — and the one most often quietly dropped to a serial `for` loop that idles
    every core but one (a 50-cell sweep ran ~5× slower serial than it needed to). ALWAYS wrap the sweep in one
    `joblib` call — `Parallel(n_jobs=-2)(delayed(run_one)(cfg) for cfg in grid)` (`-2` = all cores but one).
    joblib is installed on this stack and MEASURED working here (svd/lstsq sweep, ~5× speedup, no crash); its
    `loky` backend serializes `run_one` via cloudpickle and caps each worker's inner BLAS threads, so it
    sidesteps BOTH the oversubscription trap AND the macOS + Python-3.x `spawn` footguns that sink a
    hand-rolled pool. If you ever DO hit `BrokenProcessPool`, `AttributeError: module '__main__' has no
    attribute …`, or "an attempt has been made to start a new process before the current process has finished
    its bootstrapping phase", that is a SETUP bug (the worker fn must live in an IMPORTABLE module, the launch
    must sit under `if __name__ == "__main__":`) — fix it or stay on joblib; it is NEVER a reason to retreat to
    a serial loop, and it is NOT a BLAS/LAPACK problem (BLAS-thread env vars do not cause it). Only if joblib
    is genuinely unavailable, hand-roll a `ProcessPoolExecutor` of ≈ `cores − 2` with the function module-level,
    the launch under a `__main__` guard, and `os.environ["OMP_NUM_THREADS"]="1"` (etc.) set BEFORE importing
    numpy. When SEVERAL such scripts may run at once (the wave fires them concurrently), the core budget is
    SHARED across them — size each script's n_jobs ≈ `cores ÷ concurrent-scripts` so the two levels never
    stack into N× oversubscription. (Exception, OOM ONLY: the partition remedy DOES reduce parallel WIDTH,
    even to serial, to fit memory — that is execution-level and fine; reducing the NUMBER of seeds/configs, or
    any science value, to fit memory is down-scaling = FORBIDDEN.)
  - **One big run** (a single large solve / a training loop with big matmuls): no pool; vectorize, then
    give BLAS all probed cores.
- **Don't pre-optimize** — get one correct full-scale step, profile to find the real bottleneck
  (`torch.profiler` or a coarse timer), then optimize that. Utilization serves correctness, never the reverse.

## 5. Seeds, determinism, and a hard-to-forge sanity

Reproducibility is a paper-grade requirement, not a nicety:

```python
import os, random, numpy as np, torch
def seed_all(s):
    os.environ["PYTHONHASHSEED"] = str(s); random.seed(s); np.random.seed(s)
    torch.manual_seed(s); torch.cuda.manual_seed_all(s)
    torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False
```

Run the SCALE-CONTRACT's seed floor (the §4b-locked count for THIS run) for any stochastic quantity — and the GENERAL rule: SWEEP every
control that is NOT the variable under test across its grid. A result that holds only at one seed / one
hyperparameter / one working point is special-point hacking, not a finding; report **mean ± dispersion**
across the grid. A single-seed or single-point number is a draft, never paper-grade. `cudnn.benchmark=False` trades a little speed for determinism; keep it off for the
reported runs.

**Discriminative sanity (the auditor re-reads your log).** Every experiment must print a self-check that an
INDEPENDENT computation agrees — not a field-presence check, never a bare `print("PASS")`. Make it hard to
forge:

```python
# a quantity computed two independent ways must agree to a tight tolerance
assert abs(loss_manual - loss_autograd) < 1e-6, "SANITY FAIL: manual vs autograd loss disagree"
print(f"SANITY ok: manual={loss_manual:.8f} autograd={loss_autograd:.8f} (agree <1e-6)")
# other good forms: residual matches a QR solve to ~1e-11; a conserved quantity stays conserved;
#                   a closed-form limit matches the numerical one.
```

Cross-validation proves the number is REAL; it does NOT prove the experiment tests the CLAIM. So every
segment ALSO needs a **claim-correspondence assertion** (HANDOFF Phase-5 DISCRIMINATIVE SANITY (c)): name the
ONE load-bearing structural property the claim asserts of the METHOD, and assert the code exhibits it. Check
the STRUCTURAL half at author time (cheap, on the code, before the science run); the BEHAVIORAL half off the
run output:

```python
# STRUCTURAL (author time): a "nonlinear" forward model must depend on the state.
A1, A2 = build_operator(u_a), build_operator(u_b)          # distinct states
assert not np.allclose(A1, A2), "CLAIM FAIL: operator is state-INDEPENDENT — a constant A is a LINEAR model, not the claimed nonlinear one"
# BEHAVIORAL (result time): an "assimilation lowers error" claim must beat the no-observation run.
assert err_with_obs < err_no_obs, f"CLAIM FAIL: observations made it WORSE ({err_with_obs:.2e} vs {err_no_obs:.2e}) — the method is not assimilating"
```

A real number from a method that fails its own claim-correspondence assertion is the worst case: it clears
every provenance gate yet tests nothing the claim is about. A violation is an **S9** (the experiment does not
implement the claim), surfaced at the wave boundary — NEVER tuned away and NEVER absorbed as a reportable
negative number.

When the run reproduces an EXISTING paper number, the discriminative sanity is **reproduce-before-compare**
(see `experiment-run` — its tiering section is standalone-/review-only and says so itself): recompute the paper's number with the paper's OWN
metric and print got-vs-paper + within-tolerance BEFORE any new comparison. A mismatch is a finding,
surfaced — never tuned away.

## 深挖参考(按需)

加载本 skill 时下列参考文件**不注入**；仅在遇到对应问题时主动读取:

- [`reference/profiling-and-oom.md`](reference/profiling-and-oom.md) — OOM 诊断与内存分析：遇到 OOM 或显存不足时读，包含 `torch.profiler`、`memory_profiler`、CUDA 显存追踪等具体命令。
- [`reference/pytorch-single-gpu.md`](reference/pytorch-single-gpu.md) — 单卡训练调优：遇到单卡训练慢、mixed-precision、`torch.compile`、DataLoader 调参等问题时读。
- [`reference/scientific-computing-gpu.md`](reference/scientific-computing-gpu.md) — 科学计算 GPU 加速：遇到 NumPy/SciPy/JAX/CuPy 的 GPU 迁移问题时读。
- [`reference/distributed-quantization-trl.md`](reference/distributed-quantization-trl.md) — 分布式训练与量化（TRL/PEFT/bitsandbytes）：遇到多卡、量化或 RLHF 微调问题时读。
