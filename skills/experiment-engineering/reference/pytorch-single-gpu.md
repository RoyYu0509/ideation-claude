# Reference — 单卡 PyTorch 榨干 GPU（吞吐 + 显存）

> 由 `experiment-engineering/SKILL.md` 在需要单卡 PyTorch 优化细节时按需 Read。
> 版本基线：PyTorch 2.7–2.12，凡 API 在版本间变动的逐条标注，代码均为已核实真实 API。

---

## 1. 精度加速

### 1.1 TF32 — Ampere+ 上几乎免费的 ~3–8× matmul 提速 ⚠️ API 已换代

**瓶颈**：fp32 matmul/conv 不走 Tensor Core。TF32（10-bit 尾数）让 fp32 张量在 Tensor Core 上跑，吞吐逼近 fp16，调用方代码无需改 dtype。

**关键事实**：PyTorch **1.12 起默认关闭 TF32**（`highest`），且**不发任何 warning**——你的 fp32 训练默认就是慢的。

**⚠️ 2.9 起 API 换代**：旧的 `torch.backends.cuda.matmul.allow_tf32` / `torch.backends.cudnn.allow_tf32` **在 2.9 之后被废弃**，继续用会刷 deprecation warning。新 API：

```python
# === 新 API（PyTorch 2.9+ 推荐）===
torch.backends.cuda.matmul.fp32_precision = "tf32"   # matmul 走 TF32；"ieee" = 纯 fp32
torch.backends.cudnn.conv.fp32_precision   = "tf32"   # 卷积走 TF32

# === 跨版本最稳：一行盖住 matmul（只管 matmul，不管 conv）===
torch.set_float32_matmul_precision("high")   # "high"/"medium" → 开 TF32；"highest"(默认) → 关
```

`set_float32_matmul_precision`：`"highest"`=纯 fp32（默认，慢）；`"high"`=TF32/bf16x3；`"medium"`=bf16 内部累加。**只管 matmul**——CNN 还要单独设 `cudnn.conv.fp32_precision`/`cudnn.allow_tf32`。

**加速比**：A100 上 fp32→TF32 matmul 理论 8× FLOPS，端到端常见 **2–3×**。完全免费。
**别用**：精度敏感数值求解（TF32 只有 ~3 位十进制有效数字）；已全程 bf16/fp16 autocast 时无额外收益。
**坑**：`torch.compile` 的 `max-autotune` 默认就用 TF32，可能让对照实验莫名掉精度；新旧 API 混用会冲突，二选一。

### 1.2 bf16 vs fp16 autocast

**核心结论**：**Ampere(SM80)/Hopper 上训练一律 bf16**，不要 fp16。bf16 保留 fp32 的 8-bit 指数，动态范围一致，**不需要 GradScaler、不会 inf/NaN 溢出**；代价是尾数 7 位（fp16 是 10 位），绝对精度略低，训练几乎不受影响。

```python
# bf16：无需 GradScaler
with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
    loss = model(x)
loss.backward(); opt.step(); opt.zero_grad(set_to_none=True)

# fp16：必须 GradScaler，否则小梯度 underflow 到 0
scaler = torch.amp.GradScaler("cuda")          # torch.cuda.amp.GradScaler 已 deprecated
with torch.autocast(device_type="cuda", dtype=torch.float16):
    loss = model(x)
scaler.scale(loss).backward()
scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
```

**autocast 官方强制留 fp32 的 op**（数值敏感）：`softmax, log_softmax, layer_norm, group_norm, cross_entropy, nll_loss, binary_cross_entropy_with_logits, mse_loss, l1_loss, kl_div, exp, log, pow, cumsum, prod, sum, norm, normalize, dist, cdist, reciprocal, rsqrt, sinh/cosh, tan, acos/asin, erfinv` 等。
**降到 16-bit 的 op**（吞吐瓶颈、数值稳健）：`matmul, mm, bmm, addmm, baddbmm, linear, conv1d/2d/3d, conv_transpose*, mv, prelu, *RNN/GRU/LSTMCell`。
直觉：**GEMM/conv 降精度；规约/指数/loss 留 fp32**。

**何时用 fp16**：纯推理在 bf16 支持弱的旧卡（V100/Turing）；下游 kernel 只接 fp16。
**fp16 坑**：忘 GradScaler → 几百步后 NaN；autocast 区内手动 `.half()` 权重会绕过 fp32 白名单直接溢出（正确用法是**权重保持 fp32**，autocast op 级动态转）；grad clip 必须先 `scaler.unscale_(opt)` 再 clip。

### 1.3 隐藏开关：fp16/bf16 GEMM 的 reduced-precision 累加

Ampere+ 默认对 fp16/bf16 GEMM 用降精度累加（split-K 在 16-bit），大 K 维掉精度：

```python
torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction = False   # 强制 fp32 累加
torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction = False
```
**何时关**：大 contraction 维（长序列 attention logits、大 hidden）训练发散时，第一个该试的开关。代价是 GEMM 略慢。

---

## 2. Attention — SDPA 与 FlashAttention 命中

### 2.1 `scaled_dot_product_attention` 与 backend 选择

`F.scaled_dot_product_attention`（SDPA）是融合 attention 入口，CUDA 上自动在四个 backend 间派发：**FlashAttention-2**、**Memory-Efficient（xFormers 系）**、**cuDNN Attention**、**Math**（朴素 fallback）。

**显存**：朴素 attention 显式构造 `n×n` scores → **O(n²) 激活显存**；FlashAttention/mem-efficient 用 online-softmax 分块，**永不落地完整 n×n → 激活显存 O(n)**。长序列能不能跑起来的分水岭。

```python
from torch.nn.attention import sdpa_kernel, SDPBackend

with sdpa_kernel([SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION]):
    out = F.scaled_dot_product_attention(q, k, v, is_causal=True, dropout_p=0.0)

# 想严格只用 Flash、命不中就报错以便诊断：
with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
    out = F.scaled_dot_product_attention(q, k, v, is_causal=True)
```
> 旧 `torch.backends.cuda.sdp_kernel(enable_flash=...)` 已 deprecated，换 `torch.nn.attention.sdpa_kernel` + `SDPBackend`。

### 2.2 怎么确保命中 FlashAttention（最高频踩坑点）

不满足硬性输入限制会**静默回退**（你以为开了 Flash，显存还是 O(n²)）。命中条件：

- **dtype 必须 fp16 或 bf16**——**fp32 永远命不中**（最常见的"为什么没生效"）。
- **head_dim ≤ 256**，且通常要 8 的倍数。
- q/k/v 最后一维**连续**；`enable_gqa=True` 仅 Flash/Math 支持。
- **变长/causal**：用 `is_causal=True` 而**不要**自己传下三角 `attn_mask`（会踢回 mem-efficient/Math）。**`attn_mask` 与 `is_causal` 不能同时给**。
- 变长 batch（packed）：内建 SDPA 处理弱，高效要 `flash-attn` 包的 `flash_attn_varlen_func`（cu_seqlens 接口）。

**诊断命没命中**：用 `SDPBackend.FLASH_ATTENTION` 单独包一层，命不中会直接抛 RuntimeError 而非静默回退，据此定位是 dtype / head_dim / mask 哪条违反。

### 2.3 `flash-attn` pip 包 vs 内建 SDPA

- **内建 SDPA**：免依赖、自动多 backend 回退、和 `torch.compile` 融合好。**默认首选**。
- **`flash-attn` 包**：能拿到 **FlashAttention-3**（Hopper FP8、warp-specialization）、`varlen`、ALiBi、自定义 bias。FA-3 在 H100 长序列比 FA-2 再快 ~1.5–2×。代价：编译耗时极长、对 CUDA/torch 版本敏感、易 ABI 不匹配。
- **取舍**：常规训练用 SDPA；要 FA-3/FP8 attention 或 packed 变长高吞吐才上 `flash-attn` 包。

**坑**：`dropout_p` 不会因 `model.eval()` 自动归零——SDPA 总按传入 `dropout_p` 施加，推理必须显式传 `dropout_p=0.0`。

---

## 3. torch.compile

```python
model = torch.compile(model)                          # 默认：平衡，编译快
model = torch.compile(model, mode="reduce-overhead")  # 小 batch/推理：CUDA Graphs 杀 launch 开销
model = torch.compile(model, mode="max-autotune")     # 大 batch/固定形状：Triton 自动调优，最久最快
model = torch.compile(model, fullgraph=True)          # 禁止 graph break，有就报错
```

| mode | 干什么 | 何时用 |
|---|---|---|
| `default` | Inductor 融合，编译开销低 | 通用首选 |
| `reduce-overhead` | 启用 **CUDA Graphs** 消 CPU launch 开销；需静态形状 | 小 batch、推理、kernel 多而碎、**CPU-bound** 收益最大 |
| `max-autotune` | Triton/模板 GEMM 穷举调优，GPU 默认开 CUDA Graphs | 形状固定的大模型训练/批量推理；编译慢峰值最快 |

**与 CUDA Graphs**：`reduce-overhead`/`max-autotune` 把整段计算录成图重放，省 kernel 的 CPU dispatch；**要求静态形状、固定控制流**，与 `dynamic=True` 基本不兼容。CPU-bound 收益最大，GPU-bound 几乎无感。

**dynamic shapes 坑**：每遇新形状可能触发**重编译**，形状抖动（变长 seq/变 batch）会反复编译反而更慢。规避：优先 **bucketing/padding** 到固定几档，而非 `dynamic=True`；`torch._dynamo.config.cache_size_limit` 撞顶会**直接退回 eager**。

**graph break 诊断**（`.item()`、依赖数据的控制流、print、未支持库调用都会 break，每个 break 吃掉融合收益）：
```bash
TORCH_LOGS="graph_breaks" python train.py     # 只看 break 原因（推荐起手）
TORCH_LOGS="recompiles"   python train.py     # 看为什么重编译
```
```python
torch.compile(model, fullgraph=True)          # 有 break 直接抛错并指位置——CI 防回归
torch._dynamo.explain(model)(*inputs)         # 程序化列出所有 break
```

**何时反而变慢/报错**：`max-autotune` 首次编译达数分钟，短 job/频繁变形状别 compile；CUDA Graphs 模式下动态形状或 graph break 密集会更慢；自定义 CUDA/Triton kernel 未注册 fake/meta tensor 会报错；`max-autotune` 默认 TF32 导致与 eager 数值对不上。用 `TORCHINDUCTOR_CACHE_DIR` 让重启复用编译产物。

---

## 4. 显存工程

### 4.1 Activation / Gradient Checkpointing

**瓶颈**：训练显存大头是**激活**（要存到 backward）。Checkpointing 只存边界激活、backward 重算。N 层均匀分段：激活显存 O(N)→**≈O(√N)**，代价 **多一次 forward ≈ +33% 算力**。

```python
from torch.utils.checkpoint import checkpoint, checkpoint_sequential
y = checkpoint(block, x, use_reentrant=False)                       # 显式 use_reentrant=False（未来默认）
y = checkpoint_sequential(model_seq, segments=4, input, use_reentrant=False)
```

**为什么必须 `use_reentrant=False`**：reentrant 版整段重算、不记录 autograd 图、与 `torch.autograd.grad()` 和 detached tensor 不兼容；non-reentrant 记录图、按需停止重算、支持嵌套，且**未来版本默认 `False`**。

**进阶 SAC（Selective Activation Checkpointing）**：只重算便宜 op（element-wise、norm），保留贵的（matmul、attention），用 policy 函数控制重算/保存比，算力代价远小于全量。长序列 Transformer 现代做法。

**别用**：GPU-bound 且显存够（白搭 +33%）；推理（无 backward）。
**坑**：被 checkpoint 的函数含随机性（dropout/BN）而没保存/重放 RNG → 两遍 forward 不一致、梯度错；BN running stats 被更新两次。

### 4.2 `zero_grad(set_to_none=True)`
把 `.grad` 置 `None`（释放显存）而非填 0，省一次写全 0 kernel，backward 首次累加变直接赋值。现代 PyTorch 已默认，但显式写更稳。**行为差异**：未参与 backward 的参数 `.grad` 是 `None`，依赖 `.grad` 恒非 None 的旧代码会 `AttributeError`。

### 4.3 Fused / foreach AdamW

```python
opt = torch.optim.AdamW(model.parameters(), lr=3e-4, fused=True)   # 单 kernel 跑完整步更新
```
朴素 AdamW 每参数张量发 ~6 个 kernel，百万参数下**单步 30–120ms、占 wall-clock 20–40%**。
- **`foreach=True`（默认）**：同形状参数打包 TensorList 横向融合，但**临时峰值 ≈ 一份完整参数大小**，大模型可能 OOM。
- **`fused=True`**：单 fused CUDA kernel，纵+横向融合，**最快且峰值显存最低**。生产首选。
- **坑**：早期版本 fp16/AMP 下 loss 比 unfused 略差（新版已修），精度敏感复现值得对照一次；对 CUDA Graph 有额外约束。

### 4.4 显存峰值/碎片定位：`_record_memory_history` + snapshot

OOM 但 `nvidia-smi` 看着没满 = **碎片**（reserved ≫ allocated）。

```python
torch.cuda.memory._record_memory_history(max_entries=100_000)   # 训练前开
# ... 跑几个 step / 触发峰值 ...
torch.cuda.memory._dump_snapshot("mem_snapshot.pickle")
torch.cuda.memory._record_memory_history(enabled=None)          # 关
```
把 `.pickle` 拖到 **https://pytorch.org/memory_viz**：看每块分配的**调用栈**、生命周期、峰值时刻、碎片空洞。定位"谁吃了峰值/为什么碎"的唯一可靠手段。

### 4.5 `expandable_segments` 缓解碎片

```bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```
用 CUDA 虚拟内存（VMM）让段按需增长/收缩，物理页映射到连续虚拟段，**显著降碎片**。变长序列/动态形状常靠它把"虚假 OOM"救回来。
- **坑**：与 `backend:cudaMallocAsync` 互斥；`_record_memory_history` 在 `cudaMallocAsync` 后端下不工作（调试碎片别同时开 async 后端）。
- 其他：`max_split_size_mb:128`（限大块切分控碎片）、`garbage_collection_threshold:0.8`。

---

## 5. 数据管线

```python
loader = DataLoader(ds, batch_size=...,
    num_workers=N,            # 起点：物理核数；CPU 解码重则≈核数
    persistent_workers=True,  # 跨 epoch 不销毁 worker（num_workers>0 才有意义）
    prefetch_factor=4,        # 每 worker 预取 batch 数（默认 2）
    pin_memory=True,          # 锁页内存 → H2D 可异步
    drop_last=True)           # 固定 batch 形状，利好 CUDA Graphs/compile
for x, y in loader:
    x = x.to("cuda", non_blocking=True)   # 配合 pin_memory 才真异步
```
- `pin_memory=True` + `.to(non_blocking=True)` **必须成对**——只设一个，传输仍同步阻塞。
- **判断 GPU 被数据饿着**：`nvidia-smi` GPU-Util 在 40–70% 反复跳水、功耗上不去 → 大概率数据管线瓶颈。粗测：把一个 batch 缓存住反复 train，若吞吐立刻大涨，瓶颈确在数据。
- **坑**：`num_workers` 不是越大越好——超过 CPU/IO 承载后反而更慢（worker 争抢、IPC、`/dev/shm` 打满），要实测扫拐点。

---

## 6. 其他高 ROI

### 6.1 `channels_last` — CNN 的免费提速
```python
model = model.to(memory_format=torch.channels_last)
x = x.to(memory_format=torch.channels_last)
```
Tensor Core 要 NHWC，PyTorch 默认 NCHW，cuDNN 每次 conv 隐式转置。设 channels_last 让 NHWC 全程贯穿。**fp16 CNN 常见 1.2–1.8×，几乎零成本**。别用：纯 FC/Transformer（无意义）；纯 fp32。坑：混入不支持 channels_last 的 op 会来回转换反而更慢，profile 确认无反复 reformat；5D 用 `channels_last_3d`。

### 6.2 手动 CUDA Graphs
当 `torch.compile` 因 graph break 用不上、但重度 CPU-bound（海量小 kernel）时手动捕获（预热→`torch.cuda.graph(g)` 捕获→`copy_` 进静态 buffer + `g.replay()`）。**硬约束**：输入地址固定、形状/控制流固定、捕获区无 CPU 同步（`.item()`/print）。绝大多数情况优先 `torch.compile(mode="reduce-overhead")`（它就是自动 CUDA Graphs）。

### 6.3 推理：`inference_mode` vs `no_grad`
```python
with torch.inference_mode():     # 推理首选，比 no_grad 更快（额外关 version counter/view tracking）
    out = model(x)
```
代价：inference_mode 下创建的张量不能再参与 autograd（要回训练图用 `no_grad`）。两者都不替代 `model.eval()`（切 BN/Dropout），**都要**。

---

## 速查：一段"开箱榨干"的训练前置

```python
import torch
torch.set_float32_matmul_precision("high")                  # TF32 matmul（2.9+ 跨版本最稳）
torch.backends.cudnn.conv.fp32_precision = "tf32"           # TF32 conv（2.9+；旧版 cudnn.allow_tf32=True）
torch.backends.cudnn.benchmark = True                       # 固定输入形状时自动选最快 conv 算法
# 环境变量（进程启动前）：PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

model = model.to("cuda", memory_format=torch.channels_last) # CNN 才加 channels_last
opt   = torch.optim.AdamW(model.parameters(), lr=3e-4, fused=True)
model = torch.compile(model)                                # 形状稳定且 job 够长才值得

for x, y in loader:                                          # loader: pin_memory + persistent_workers + prefetch_factor
    x = x.to("cuda", non_blocking=True, memory_format=torch.channels_last)
    with torch.autocast("cuda", dtype=torch.bfloat16):      # Ampere+ 训练用 bf16，免 GradScaler
        loss = loss_fn(model(x), y.to("cuda", non_blocking=True))
    loss.backward()
    opt.step(); opt.zero_grad(set_to_none=True)
```

---

## 版本敏感点（随 PyTorch 升级复核）

1. **TF32 API 换代**（最重要）：`allow_tf32` 系列在 2.9 后废弃 → `…fp32_precision = "tf32"/"ieee"`；跨版本最稳 `set_float32_matmul_precision("high")`（只管 matmul）。
2. **AMP**：`torch.cuda.amp.*` 旧式 → `torch.autocast("cuda",...)` / `torch.amp.GradScaler("cuda")`。
3. **SDPA**：`torch.backends.cuda.sdp_kernel()` 已废 → `torch.nn.attention.sdpa_kernel([SDPBackend.*])`。
4. **checkpoint**：必须显式 `use_reentrant=False`。
5. **FlashAttention 命中三铁律**：dtype 必须 fp16/bf16（fp32 永不命中）、head_dim ≤ 256、`is_causal=True` 而非显式 causal mask（且二者互斥）。

**Sources**：[CUDA semantics 2.12](https://docs.pytorch.org/docs/2.12/notes/cuda.html) · [set_float32_matmul_precision](https://docs.pytorch.org/docs/2.12/generated/torch.set_float32_matmul_precision.html) · [TF32 默认关 #153195](https://github.com/pytorch/pytorch/issues/153195) · [TF32 API 废弃 #159440](https://github.com/pytorch/pytorch/issues/159440) · [AMP 文档](https://docs.pytorch.org/docs/2.12/amp.html) · [SDPA 文档](https://docs.pytorch.org/docs/2.12/generated/torch.nn.functional.scaled_dot_product_attention.html) · [SDPA 教程](https://docs.pytorch.org/tutorials/intermediate/scaled_dot_product_attention_tutorial.html) · [checkpoint 文档](https://docs.pytorch.org/docs/main/checkpoint.html) · [Activation Checkpointing/SAC blog](https://pytorch.org/blog/activation-checkpointing-techniques/) · [AdamW fused #158371](https://github.com/pytorch/pytorch/issues/158371) · [torch_cuda_memory 文档](https://docs.pytorch.org/docs/main/torch_cuda_memory.html) · [CUDA caching allocator DevLog](https://docs.pytorch.org/devlogs/eager/2026-06-01-cuda-caching-allocator/) · [channels_last blog](https://pytorch.org/blog/accelerating-pytorch-vision-models-with-channels-last-on-cpu/)
