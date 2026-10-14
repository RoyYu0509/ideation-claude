# Reference — GPU 瓶颈诊断方法论 + OOM 工程

> 由 `experiment-engineering/SKILL.md` 在"不知道该优化什么/util 高却慢/OOM"时按需 Read。**这是把黑魔法用对地方的前提——先量瓶颈，再选优化。**
> 适用 NVIDIA GPU + PyTorch（CUDA 12.x / PyTorch 2.5–2.12）。带 `_` 前缀 API（如 `_record_memory_history`）是内部接口，跨版本可能变动，生产脚本做 `hasattr` 兜底。

## 0. 核心心法：先量瓶颈，再选优化（不要反过来）

`nvidia-smi` 显示 `GPU-Util 100%` **不代表算力被榨满**。`GPU-Util` 的官方定义只是"过去采样周期内至少有一个 kernel 在跑的时间占比"——衡量"有没有在动"，不衡量"动得有多满"。实测中存在 `GPU-Util=100%` 但 SM occupancy <20%、只用约 20% 峰值算力（一个 memory-bound kernel 在"满负荷空转"）。

诊断第一步永远是**给瓶颈归类**——归类决定优化方向，选错类别技巧全白费：

| 瓶颈类别 | 现象 | 该上的优化 | 上错了的（无效甚至更糟） |
|---|---|---|---|
| **Compute-bound** | 算术强度高，SM/Tensor Core 真在算 | 低精度（bf16/fp8）、张量核、更大 GEMM | 减少访存（已不是瓶颈） |
| **Memory-bandwidth-bound** | util 高但算力低，DRAM throughput 顶满 | 算子融合、减少 HBM 往返、提高数据复用、`torch.compile` | 上 fp8/张量核（算得再快喂不饱） |
| **IO/CPU-bound** | util 时高时低、规律掉零；trace 上 kernel 间大片空隙 | 修 DataLoader、预处理搬上 GPU、减少 `.item()` 同步、`non_blocking` | 任何 GPU 端 kernel 优化（GPU 没在等算力） |

---

## 1. Roofline 思维（瓶颈分类的理论框架）

两条硬件上限：水平 **compute roof**（峰值算力）、斜的 **memory roof**（峰值 HBM 带宽）。横轴 **算术强度** = 有用浮点运算数 / 从显存搬运字节数（FLOP/byte）。算术强度**低** → memory-bound；**高** → compute-bound。交点 **ridge point（脊点）** 横坐标 = 峰值 FLOPS ÷ 峰值 HBM 带宽 = "逃离带宽瓶颈所需最小算术强度"。

**判读标准（可直接抄）——kernel 算术强度低于本卡脊点就是 memory-bound：**

| GPU | 峰值 bf16 FLOPS（稠密） | HBM 带宽 | **脊点 (FLOP/byte)** |
|---|---|---|---|
| **H100 SXM** | 9.89e14 | 3.35 TB/s | **≈295** |
| **A100-80GB** | 3.12e14 | ~2.0 TB/s | **≈156**（按公式推，以实测带宽核对） |

经验法则："GPU 上这个数接近 **300**"。直觉：只有每从 HBM 搬 1 字节、配上约 300 次 bf16 运算，才可能吃满 H100 算力。这解释了为什么逐元素/激活/LayerNorm/softmax/小 batch GEMV 几乎总 memory-bound，而大 GEMM/大 batch 才容易 compute-bound。
> ⚠️ 用**无稀疏**稠密峰值算脊点/MFU。NVIDIA marketing 常报含 2:4 稀疏的翻倍数（H100 "1979 TFLOPS"）——稠密训练够不到，用它会系统性低估利用率。

算术强度<脊点（memory-bound）→ 查访存、kernel 融合，上低精度张量核**无用**；>脊点（compute-bound）→ 才该上低精度/张量核/更优 GEMM。Nsight Compute 直接画 roofline 并自动判定（§5）。

---

## 2. MFU / HFU：比 nvidia-smi 真实得多的利用率

**MFU (Model FLOPs Utilization)** = 实测吞吐对应的"模型必需 FLOPs" ÷ 峰值 FLOPs（只数前向+反向数学必需，不数重计算）。

**实测公式（Transformer，可直接抄）：**
```
MFU ≈ (6 × N_params × tokens_per_sec) / peak_FLOPS
```
- 系数 **6** = 每 token 每参数 FLOPs（前向 2 + 反向 4）。
- `peak_FLOPS` 用本卡**稠密 bf16** 峰值（H100=9.89e14，A100=3.12e14）；多卡分母 ×n_gpus。

**HFU (Hardware FLOPs Utilization)** = 实际跑的 FLOPs（含重计算）÷ 峰值。开梯度检查点时 HFU > MFU。例：Megatron 175B/A100-80GB，**MFU 51.4%、HFU 52.8%**。

**典型好坏区间**：大模型多机训练 **MFU 30–50% 正常偏好**；**>50% 很优秀**。到本卡现实峰值附近就停止调优、开始训练。

**用 PyTorch 自动数 FLOPs（不靠手推系数）**：
```python
from torch.utils.flop_counter import FlopCounterMode
flop_counter = FlopCounterMode(display=False)
with flop_counter:
    model(**inputs).sum().backward()
total_flops = flop_counter.get_total_flops()
# 在第 2 个 iteration 测（第 1 个有启动开销），再 / 实测耗时 / 峰值
mfu = total_flops / step_time / peak_FLOPS
```
**为什么比 nvidia-smi 真实**：`GPU-Util%` 只说"有 kernel 在跑"；MFU 拿"被榨出的有效算力 / 峰值"，骗不了人。**MFU 低 + util 高 = 强烈的 memory-bound/低效信号。**

---

## 3. 实时监控：怎么一眼看出 memory-bound

**`nvidia-smi` 关键列（区分两个"memory"和两个"util"）：**
- `Memory-Usage`（`40GB/80GB`）：**显存占用量（容量）**，和带宽无关、和"榨没榨满"无关——满了只说明 OOM 风险。
- `GPU-Util`：上面强调的"有没有 kernel 在跑"，**不是算力饱和度**。
- `Pwr:Usage/Cap`：功耗，**实战中比 util 更诚实**——真做大量 FP/张量核运算时功耗接近 TDP（H100 接近 700W）；若 util=100% 但功耗只到一半，基本是 memory-bound 空转。

```bash
nvidia-smi dmon -s pucm -o T
#  sm  = SM 利用率%   mem = 显存接口活跃时间%  ← mem 高而 sm 对应算力上不去 = 偏 memory-bound
```
> Hopper+ 有 GPM `smutil`（活跃 SM%，更接近真实占用）。要 FP/Tensor-Core 活跃%、DRAM 带宽% 这类**饱和度**指标，`nvidia-smi` 给不全，需 DCGM（`DCGM_FI_PROF_PIPE_TENSOR_ACTIVE`、`DCGM_FI_PROF_DRAM_ACTIVE`、`DCGM_FI_PROF_SM_OCCUPANCY`）或 ncu。

**交互 dashboard**：`nvitop`（`pip install nvitop`，top 式，按进程看显存/util/功耗、可 kill）；`gpustat -i 1`（最轻一行快照，多卡总览/写日志）；`nvtop`（htop 式曲线，**IO-bound 的锯齿/周期性掉零最直观**）。

**现场快速判据**：显存占用高、sm 算力/功耗上不去 → **memory-bound**；util 周期性掉零、锯齿 → **IO/CPU-bound**（§4/§6）；功耗贴 TDP、util 高且稳 → **compute-bound**（这时才去 §1 上低精度）。

---

## 4. torch.profiler：定位 kernel 间空隙 + 热点算子

```python
import torch
from torch.profiler import profile, ProfilerActivity, schedule
with profile(
    activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
    record_shapes=True, profile_memory=True, with_stack=True,
    schedule=schedule(wait=1, warmup=1, active=3, repeat=1)) as prof:
    for step, batch in enumerate(loader):
        train_step(batch); prof.step()
print(prof.key_averages(group_by_input_shape=True).table(
    sort_by="self_cuda_time_total", row_limit=20))      # 按 GPU 自身耗时排，最值钱
prof.export_chrome_trace("trace.json")
```
> `record_shapes`/`with_stack`/`profile_memory` 有额外开销，诊断时开、生产时关。

**判读标准**：
- **看 GPU gap（kernel 间空隙）= CPU/launch/数据瓶颈铁证。** 把 `trace.json` 拖进 **Perfetto UI**（ui.perfetto.dev）。GPU 流应被 kernel 几乎连续填满；若 kernel 间大片空白、CPU 行在忙 → GPU 等 CPU（数据预处理/Python 逻辑/频繁 `.item()`同步/过多小 kernel launch）→ **CPU/IO-bound**，去 §6。
- DataLoader 喂不上：每 step 开头一段 GPU 全空、CPU 在跑数据 → GPU starvation。
- `Self CUDA %` 集中在某一两个算子 → 优化目标明确；若全是逐元素/norm/激活各占一点 → 该上 **算子融合 / `torch.compile`**（memory-bound 信号）。
- **TensorBoard**：`pip install torch-tb-profiler` + `on_trace_ready=tensorboard_trace_handler("./logdir")`，自带把每步拆成 Kernel/Memcpy/DataLoader/CPU Exec，一眼看出哪块吃时间。

---

## 5. Nsight：nsys（系统级）vs ncu（kernel 级）

**先 nsys 看全局，发现可疑 kernel 再用 ncu 钻进去。**

**`nsys`（Nsight Systems）— 系统级时间线**：CPU↔GPU 重叠、H2D/D2H 传输、CUDA API、kernel gap、多流/多卡同步。回答"GPU 有没有被喂饱、时间花在哪阶段"。
```bash
nsys profile -t cuda,nvtx,osrt,cudnn,cublas \
  --capture-range=cudaProfilerApi --stop-on-range-end=true \
  -o report -f true -x true  python train.py     # 只 profile 圈定区间，否则文件巨大
```
```python
torch.cuda.cudart().cudaProfilerStart(); ...; torch.cuda.cudart().cudaProfilerStop()
torch.cuda.nvtx.range_push("forward"); ...; torch.cuda.nvtx.range_pop()   # 时间线自定义标签
```
**判读**：GPU 行大片 gap 且 CPU 在忙 → launch/数据瓶颈；H2D memcpy 和 compute 没重叠 → 上 `pin_memory`+`non_blocking=True`。

**`ncu`（Nsight Compute）— 单 kernel 级**：occupancy、访存效率、roofline 归类。开销大、会重放 kernel，只对少数热点用。
```bash
ncu --set full -o kreport -f -k regex:"gemm|attention" -c 10  python train.py
```
**判读标准（直接抄）**：
- **GPU Speed of Light**：`Compute (SM) Throughput %` vs `Memory (DRAM) Throughput %`——哪个先顶到接近峰值就是哪类 bound（DRAM% 高 SM% 低 = memory-bound）。
- 两者都 **<60%** 通常是 **latency 受限**（occupancy 不足/同步等待）→ 提 occupancy、减串行依赖。
- **Memory Workload Analysis**：L1/L2 miss 高 + DRAM 带宽顶满 = 实锤 memory-bound。
- **Occupancy**：achieved 远低于 theoretical → 受寄存器/shared memory/block 配置限制，调启动参数。

---

## 6. CPU 侧：是不是 Python/数据预处理拖累 GPU

**`py-spy`（零侵入、不改代码、可采样正在跑的进程）**：
```bash
pip install py-spy
py-spy top --pid <PID>                          # 实时看哪个 Python 函数最耗 CPU
py-spy record -o flame.svg --pid <PID> -d 60    # 录 60s 火焰图
py-spy dump --pid <PID>                         # 卡住时打印各线程栈（抓死锁/同步点）
```
**判读**：火焰图大头在 `DataLoader`/`collate_fn`/数据增广/`PIL`/`numpy` → 数据预处理瓶颈 → 加 `num_workers`/`pin_memory`/`persistent_workers`/`prefetch_factor`，或把增广搬上 GPU（DALI、`torchvision.transforms.v2` GPU 版）。大头在主线程频繁 `.item()`/`.cpu()` → 同步点强制 GPU 停等。与 torch.profiler 交叉验证结论应一致。

---

## 7. OOM 工程

### 7a. 可视化定位：谁占了显存
```python
torch.cuda.memory._record_memory_history(max_entries=100_000)   # 训练前开
try: train()
except torch.cuda.OutOfMemoryError: pass
torch.cuda.memory._dump_snapshot("mem_snapshot.pickle")
torch.cuda.memory._record_memory_history(enabled=None)          # 关，避免持续吃内存
```
把 `.pickle` 拖到 **https://pytorch.org/memory_viz**（纯前端本地解析）：按时间画每块 allocation 的**生命周期 + 分配处调用栈**，直接看出 OOM 前是谁、哪行、多大、为什么不释放（典型：激活堆积、中间结果被意外长期持有）。轻量替代：`torch.cuda.memory_summary()`、`torch.cuda.max_memory_allocated()`。

### 7b. 区分"真 OOM" vs "碎片化"（关键判读）
OOM 报错同时给 **allocated**（live 张量实占）和 **reserved**（PyTorch cudaMalloc 占住总量，含空闲块）：
- **`reserved − allocated` 很大** = **碎片化**，不是真不够。对策：`export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`（CUDA VMM 把池做成可增长/收缩的连续虚拟段，相邻空闲块能合并）。备选：`max_split_size_mb:<N>`、`garbage_collection_threshold:0.8`。
  - 注意：① 开了 `expandable_segments` 后 OOM 报错里"try expandable_segments"提示**仍可能照出**（已知噪声）；② 不能消除所有碎片（长期存活张量穿插其间，空闲块跨不过 live 块合并）；③ 小块(≤1MiB)/大块(>1MiB)分属不同池。
- **`allocated` 本身贴近上限** = **真 OOM**，走下面决策树。

### 7c. "OOM 了怎么办"对策决策树（从便宜到昂贵，逐级加码）

```
OOM
│
├─1. 先排除碎片：报错里 reserved≫allocated？
│     └─是 → PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True，常常当场解决，无精度/速度代价
│
├─2. 降 batch size + 梯度累积
│     └─有效 batch 不变、显存线性下降；几乎零代价，永远先试这个
│
├─3. 激活检查点 (activation/gradient checkpointing)
│     └─torch.utils.checkpoint，FSDP 用 apply_activation_checkpointing；关键 use_reentrant=False
│       代价：多跑一遍前向，step +~30%；换 batch 翻倍 → 多数情况净赚
│
├─4. 混合精度 (bf16/fp16, AMP)
│     └─激活/权重副本减半显存，compute-bound 时还更快；bf16 数值更稳优先
│
├─5. 量化 / Offload
│     └─权重 8bit/4bit（bitsandbytes）；优化器状态/参数 CPU offload（ZeRO-Offload/FSDP CPUOffload）；NVMe 兜底
│       代价：offload 走 PCIe，慢；显存换得最多
│
├─6. 分片 / 多卡 (FSDP / DeepSpeed ZeRO-2/3 / TP/PP)
│     └─参数+梯度+优化器状态切到多卡；单卡放不下大模型的根本解
│
└─7. 长跑稳定性：及时 .detach()、别在 list 囤带计算图的 tensor、日志只存 .item()/.detach().cpu()
      —— 否则计算图/激活随 step 单调堆积，几百步后必 OOM（慢性泄漏，非单步爆显存）
```
**经验权衡**：检查点把 step +30% 但让 batch 翻倍、避免 OOM，净训练效率仍大幅正收益——这是 2 与 3 之间最常见实战取舍。

---

## 来源（已核实，2025–2026）
- MFU/HFU 公式/系数/Megatron 实例/峰值/FlopCounterMode：[stas00/ml-engineering performance](https://github.com/stas00/ml-engineering/blob/master/training/performance/README.md)
- MFU 定义/6×N/PaLM：[Debjit Paul (2025)](https://debjitpaul.github.io/blog/2025/compute/) · [PaLM 论文](https://arxiv.org/pdf/2204.02311)
- Roofline/算术强度/脊点：[Modal GPU Glossary Roofline](https://modal.com/gpu-glossary/perf/roofline-model) · [JAX Scaling Book Roofline](https://jax-ml.github.io/scaling-book/roofline/)
- nvidia-smi util 误导/100%util 仅 ~20% 算力/DCGM：[arthurchiao Understanding GPU Performance](https://arthurchiao.art/blog/understanding-gpu-performance/) · [Trainy GPU Utilization Misleading](https://www.trainy.ai/blog/gpu-utilization-misleading)
- torch.profiler：[PyTorch Profiler Recipe 2.12](https://docs.pytorch.org/tutorials/recipes/recipes/profiler_recipe.html)
- nsys vs ncu/Speed-of-Light/<60% latency：[Nsight Compute Profiling Guide](https://docs.nvidia.com/nsight-compute/ProfilingGuide/index.html) · [mcarilli nsys PyTorch 命令](https://gist.github.com/mcarilli/376821aa1a7182dfcf59928a7cde3223)
- OOM snapshot/memory_viz：[PyTorch Memory Profiling Recipe](https://docs.pytorch.org/tutorials/beginner/mosaic_memory_profiling_tutorial.html) · [Zach DeVito Memory Snapshots](https://zdevito.github.io/2022/08/16/memory-snapshots.html) · [HF Visualize GPU memory](https://huggingface.co/blog/train_memory)
- 碎片化/expandable_segments：[PyTorch DevLog CUDA Caching Allocator (2026-06-01)](https://docs.pytorch.org/devlogs/eager/2026-06-01-cuda-caching-allocator/)

### 实事求是标注
- 脊点 H100=295 是 bf16 稠密峰值算得；A100≈156 按公式推（未取一手引用页），用时以你卡实测带宽核对。fp16/fp8/不同显存版本脊点不同，按 `峰值FLOPS÷带宽` 换算。
- MFU 30–50% 为大模型多机训练经验区间；小模型、纯推理、MoE 口径不同。
- `nvidia-smi` 的饱和度盲区（FP/Tensor-Core 活跃%、DRAM 带宽%）需 DCGM 或 ncu 补全——单靠 `nvidia-smi` 无法可靠区分 compute/memory-bound。
