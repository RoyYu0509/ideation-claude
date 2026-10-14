# Reference — 分布式 / 量化 / HuggingFace 生态黑魔法

> 由 `experiment-engineering/SKILL.md` 在需要"放不下的模型放下、训练再快一截"时按需 Read。
> 版本基线（2026-06 核实）：`transformers≈5.x`、`trl 1.6.0`、`peft 0.19.1`、`bitsandbytes 0.49.2`、`liger-kernel 0.8.0`、`accelerate`(含 FSDP2)、`deepspeed≈0.19.x`、PyTorch ≥2.9（FSDP1 自 2.11 deprecated）。版本变动快，落地前 `pip show` 复核；标 **[需核]** 处务必现场验证。

---

## 0. 先建立显存账本（一切优化的坐标系）

混合精度（bf16）下，单参数训练态显存（Adam）：

| 组件 | bytes/param |
|---|---|
| fp16/bf16 权重 | 2 |
| fp32 master 权重 | 4 |
| fp32 梯度 | 4 |
| Adam m（一阶动量） | 4 |
| Adam v（二阶动量） | 4 |
| **小计（不含激活）** | **~16–18** |

经验法则：**全量混合精度训练 ≈ 16× 参数量字节**。这就是 7B 全量微调 ≈ 112–126 GB 放不进单张 80GB 的来源；也是三条正交省显存主轴的由来——**分片**把这 16 拆到 N 卡、**量化**把权重那 2 压到 0.5、**8-bit optimizer** 把 m/v 那 8 压到 2。**激活显存**单列（∝ batch×seq×层数），由 gradient checkpointing / packing / 融合 kernel 处理。

---

## 1. 分片并行：FSDP2 与 DeepSpeed ZeRO

### 1.1 ZeRO 三 stage = 沿上表逐列分片

| | 分什么 | 每卡省（N 卡） | FSDP 对应 |
|---|---|---|---|
| **ZeRO-1** | 优化器状态(m,v,master) | 12 → 12/N | 无直接对应 |
| **ZeRO-2** | +梯度 | 再 +4/N | `reshard_after_forward=False` 近似 |
| **ZeRO-3** | +参数本身 | 全 16 → 16/N | **`FULL_SHARD`（FSDP 默认）= ZeRO-3** |

ZeRO-3/FULL_SHARD 代价：每个 fwd/bwd 都 all-gather 当前层完整参数、用完即丢，通信量最大；用 prefetch 把通信藏到计算后面。

### 1.2 FSDP2 / `fully_shard`（取代 FSDP1 `FullyShardedDataParallel`）

FSDP2 核心：**per-parameter sharding**，参数 dim-0 切分变 `DTensor`。相比 FSDP1（FlatParameter 打平）：frozen 参数约束放松（LoRA 友好）、sharded state_dict 免通信、与 TP/PP device mesh 更自然。

```python
from torch.distributed.fsdp import fully_shard, MixedPrecisionPolicy
mp = MixedPrecisionPolicy(param_dtype=torch.bfloat16, reduce_dtype=torch.float32)
for layer in model.layers:          # 先逐层 wrap（每层一个通信单元）
    fully_shard(layer, mp_policy=mp)
fully_shard(model, mp_policy=mp)     # 再 wrap 顶层
# ⚠️ FSDP2 要求 model 与 optimizer 一起传给 Accelerator.prepare()
```

经 transformers `Trainer`（推荐路径），`TrainingArguments`：
```python
TrainingArguments(
    fsdp="full_shard auto_wrap",
    fsdp_config={
        "fsdp_version": 2,                       # 2=FSDP2 [需核]
        "transformer_layer_cls_to_wrap": "LlamaDecoderLayer",
        "reshard_after_forward": True,           # False=省一次 re-all-gather 但峰值更高（≈ZeRO-2）
        "activation_checkpointing": True,        # FSDP 下用它，别再叠 HF gradient_checkpointing
        "cpu_offload": False,
    })
```
> **坑**：FSDP2 下 `trainer.evaluate()` 在 `train()` 前调用会报 "model and optimizer must be passed together to prepare()"；tied embedding（`lm_head.weight`）偶发 `KeyError`；`activation_checkpointing`（FSDP 原生）与 `gradient_checkpointing`（HF）**二选一**，叠加出问题。

### 1.3 三种 offload，代价递增

| 手段 | 挪走什么 | 省多少 | 代价 |
|---|---|---|---|
| **CPU offload** | ZeRO-3/FSDP 分片再下沉 CPU RAM | 几乎清零权重显存 | PCIe 搬运，**慢 2–10×** |
| **NVMe offload**（ZeRO-Infinity，**DeepSpeed 独有**） | 优化器/梯度/部分权重→NVMe | 单卡训"放不下"的超大模型 | 最慢；强依赖高速 NVMe；FSDP 无此能力 |
| **Activation offloading** | 仅前向激活→CPU，反向取回 | 激活显存大降 | 额外 H2D/D2H；与 checkpointing 互补 |

DeepSpeed `deepspeed_config.json`：`"offload_optimizer": {"device":"cpu"|"nvme","nvme_path":"/local_nvme"}`、`"offload_param":{...}`。**FSDP vs DeepSpeed 关键差异**：FSDP offload 全有或全无，DeepSpeed 可逐项 + NVMe，控制更细。两者都已进 accelerate，切换只换 config。

**prefetch**：`--fsdp_forward_prefetch`/`--fsdp_backward_prefetch`（DeepSpeed `stage3_prefetch_bucket_size`）提前 all-gather 下一层、overlap 到当前计算，用一点显存换吞吐，多卡 ZeRO-3/FSDP 几乎必开。

---

## 2. 量化训练：bitsandbytes 8-bit / 4-bit + QLoRA

### 2.1 权重量化（压上表那 2 bytes）
```python
from transformers import BitsAndBytesConfig, AutoModelForCausalLM
import torch
cfg4 = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",            # NF4：对正态分布权重信息论最优；训练用 nf4
    bnb_4bit_use_double_quant=True,       # 双重量化：量化常数再量化，额外省 ~0.4 bit/param
    bnb_4bit_compute_dtype=torch.bfloat16 # 反量化后计算 dtype，默认 fp32 慢，务必设 bf16
)
model = AutoModelForCausalLM.from_pretrained(model_id, quantization_config=cfg4, dtype="auto")
```
4-bit 权重显存 ≈ **原 fp16 的 1/4**（13B 可塞进 16GB T4：seq 1024 / bsz 1 / grad_accum 4）。
**坑**：`load_in_4bit/8bit` 只支持训练**额外**参数（必须配 LoRA）；CPU offload 出去的权重以 fp32 存（不省）；量化只省**参数**显存，激活密集模型基本无益。

### 2.2 8-bit optimizer（压上表那 8 bytes 的 m/v → 2）
```python
import bitsandbytes as bnb
opt = bnb.optim.AdamW8bit(model.parameters(), lr=2e-4)         # 优化器状态显存约 −75%
opt = bnb.optim.PagedAdamW8bit(model.parameters(), lr=2e-4)    # paged：显存尖峰换页到 CPU，吸收 OOM 尖峰
```
可用：`Adam8bit/AdamW8bit/PagedAdam8bit/PagedAdamW8bit/PagedAdamW32bit/Lion8bit/RMSprop8bit`。**paged vs 非 paged**：paged 不额外省稳态显存，而用 unified memory 在显存吃紧瞬间把状态搬 CPU、防 OOM 崩溃。默认 **<4096 元素张量自动留 32-bit**（bias/LN）。Trainer 一行：`TrainingArguments(optim="paged_adamw_8bit")`。

---

## 3. PEFT：LoRA / QLoRA / DoRA 的显存账

**为什么 LoRA 能单卡调 7B/13B**：冻结主干 → master/m/v 这 12 bytes/param **只对 adapter 算**（adapter 通常 <1% 参数）；主干再被 4-bit 压到 0.5 bytes/param。7B 全量 ~112GB → QLoRA ~6–10GB。

```python
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
model = prepare_model_for_kbit_training(model)     # 4-bit 训练前置：开 GC、LN/lm_head 转 fp32、修 requires_grad
cfg = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules="all-linear",   # QLoRA 配方：注入所有 Linear，效果接近全量
    use_dora=False, use_rslora=False, task_type="CAUSAL_LM")
model = get_peft_model(model, cfg)
```
- **`target_modules`**：`"all-linear"`（质量最高）↔ 仅 `q_proj,v_proj`（最省）。MoE 专家权重是 `nn.Parameter` 非 Linear，要 `target_parameters=[...]` 点名，但推理会因物化全部专家变慢 → **务必 merge**。
- **DoRA**（`use_dora=True`）：幅度+方向分解，低 r 下质量优于 LoRA。代价（4090,Llama-3.1-8B）：比 LoRA **+139% 时间 / +4% 显存**；仅支持 embedding/linear/Conv2d；+DeepSpeed ZeRO-2 有已知 bug。
- **merge**：`model = model.merge_and_unload()`（**非原地，必须接收返回值**）。可逆用 `merge_adapter()`/`unmerge_adapter()`；多 adapter 加权 `add_weighted_adapter(...)`。
- **进阶初始化**（`init_lora_weights=`）：QLoRA 上配 **LoftQ/PiSSA** 降量化误差、加速收敛。
- **坑**：4-bit 量化权重不能直接 merge（先反量化）；`prepare_model_for_kbit_training` 必须在 `get_peft_model` 之前。

---

## 4. TRL / transformers 训练黑魔法（ROI 最高的一批开关）

### 4.1 Example packing —— 吞吐数倍的头号黑魔法
把多条短样本拼成接近满 `max_length` 的块，消灭 padding 浪费。`SFTConfig`（trl 1.6）：
```python
from trl import SFTConfig
SFTConfig(
    packing=True,                 # 默认 False；开启后吞吐随数据长度分布可数倍提升
    packing_strategy="bfd",       # "bfd"(best-fit decreasing) | "bfd_split" | "wrapped"
    max_length=4096,
    padding_free=True,            # 不 padding，整 batch 展平成一条连续序列 + position_ids 区隔
    completion_only_loss=None,    # None: prompt-completion 数据自动只对 completion 算 loss
    assistant_only_loss=False,    # 对话数据：只对 assistant 轮算 loss
    activation_offloading=False,
    neftune_noise_alpha=None,     # NEFTune：embedding 加噪提指令微调质量，论文用 5~15
    use_liger_kernel=True)        # 继承自 TrainingArguments，见 §5
```
> **关键关联**：`packing=True` 且 `packing_strategy="bfd"` 时，**padding-free 自动启用**，与 `padding_free` 参数值无关。

### 4.2 padding-free / position_ids
把 batch 内所有序列拍平成一条、用 `position_ids` 标边界 —— 零 padding 计算。**仅支持 FlashAttention-2/3**。配 packing 用，省"被 pad token 浪费的 FLOPs 和激活显存"。

### 4.3 只对 completion 算 loss
现代写法 `completion_only_loss`/`assistant_only_loss`（SFTTrainer 内建）。旧 `DataCollatorForCompletionOnlyLM`（response template，mask prompt label=-100）仍可用，新代码优先前者。

### 4.4 NEFTune
`neftune_noise_alpha=5~15`：训练时 embedding 加均匀噪声，指令微调质量明显提升、推理关闭、零额外参数。已下沉进 transformers `TrainingArguments`。

### 4.5 DPO/偏好训练免 ref-model
PEFT 下 `DPOTrainer` **不另存参考模型**：临时 `disable_adapter()` 还原 base 当 ref —— 省一整份模型显存。或 `precompute_ref_log_probs=True` 预算 ref logprob。**坑**：`sync_ref_model=True` 与"PEFT 无独立 ref_model"互斥，也不能与 `precompute_ref_log_probs=True` 共用。

### 4.6 `gradient_checkpointing` + `use_reentrant` 的坑（高频踩）
部分冻结（含 LoRA/冻 embedding）+ GC 时，旧 `use_reentrant=True` 会让 frozen 层输出 `requires_grad=False` → **梯度断流，loss.requires_grad=False，根本不训**。修法：
```python
TrainingArguments(gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False})  # ← 几乎总要这个
```
PEFT 侧 `model.enable_input_require_grads()` 兜底。FSDP 下改用 `activation_checkpointing`，别和 HF GC 叠。

### 4.7 `group_by_length`
`TrainingArguments(group_by_length=True)`：按长度排序分桶，同 batch 长度相近 → padding 大减。**不开 packing 时**的省 padding 手段；开了 packing 就不需要。

---

## 5. Kernel 融合

### 5.1 Liger Kernel（0.8.0）—— 一行接入、收益巨大
Triton 写的融合 kernel：**RMSNorm / RoPE / SwiGLU / CrossEntropy / FusedLinearCrossEntropy**。官方：**多卡吞吐 +20%、显存 −60%（→ 可塞 4× context）**。
```python
TrainingArguments(use_liger_kernel=True)   # 路径 A：Trainer 一行（SFTConfig 同字段）
# 细粒度：liger_kernel_config={"rope":True,"fused_linear_cross_entropy":True,"rms_norm":True,"swiglu":True,"cross_entropy":False}
from liger_kernel.transformers import AutoLigerKernelForCausalLM   # 路径 B
model = AutoLigerKernelForCausalLM.from_pretrained(model_id)
```
- **省显存主力 FusedLinearCrossEntropy (FLCE)**：把 `hidden @ lm_head` 的巨大 logits 分块、边算边算 loss，**不物化 `[batch×seq, vocab]` 全 logits**。大词表（vocab 12.8万+）收益最大。
- **互斥**：`cross_entropy` 与 `fused_linear_cross_entropy` 别同时 True（FLCE 已含 CE）。支持 35+ 架构（Llama/Mistral/Gemma/Qwen/Phi/GLM-4/Qwen2-VL）。与 FA/FSDP/DeepSpeed 兼容。
- **坑**：仅对**被支持架构**生效，冷门模型 patch 不上会静默无效 → 跑前确认架构在列表。

### 5.2 Unsloth —— 手写 kernel 路线（单卡极限）
全链路手写 Triton kernel + 自定义 GC，**单卡 2× 速度 / 显存 −70%** 量级。H100-80GB context 可到 **228K**（HF+FA2 仅 48K）。**定位**：单卡/消费级 GPU 微调首选；**多卡/超大规模仍走 FSDP/DeepSpeed**（Unsloth 多卡支持弱）。

### 5.3 xformers `memory_efficient_attention` 现状
**已基本被 PyTorch SDPA 取代**。新代码 `attn_implementation="sdpa"`（装了 FA 用 `"flash_attention_2"`/`"flash_attention_3"`）。**除非有 xformers 专属算子需求，否则直接 SDPA/FA，别再引 xformers。** FA-3 主要面向 Hopper(H100) [需核]。

---

## 6. 梯度累积 + micro-batch 的真实算术

```
effective_batch = per_device_train_batch_size × gradient_accumulation_steps × world_size
```
```python
TrainingArguments(per_device_train_batch_size=2, gradient_accumulation_steps=16)  # ×8 GPU = 256
```
- **显存关系**：峰值激活显存只由 **micro-batch × seq_len** 决定，与 grad_accum **无关**。**放不下就降 micro-batch、升 grad_accum**，保持有效 batch 不变 —— "调显存不动超参"的核心杠杆。
- **坑**：lr/warmup 步数按 optimizer step 计（非 micro-step）；历史上有 grad_accum 下 loss 归一化 bug（新版已修，跨 padding-free/packing 仍要核对 loss 量级 [需核]）。

---

## 速查：瓶颈 → 武器

| 瓶颈 | 首选武器 |
|---|---|
| 模型权重放不下（多卡） | FSDP2 FULL_SHARD / ZeRO-3 |
| 模型权重放不下（单卡） | 4-bit NF4 + QLoRA；或 Unsloth |
| 优化器状态吃显存 | 8-bit optimizer（`paged_adamw_8bit`） |
| 显存尖峰偶发 OOM | Paged optimizer + activation offloading |
| 激活显存爆（长 context） | gradient/activation checkpointing + Liger FLCE |
| 大词表 logits 爆显存 | Liger `fused_linear_cross_entropy` |
| 吞吐低、padding 浪费 | packing + padding_free（FA2/3） |
| 单卡想再快再省 | Liger 一行 / Unsloth kernel |
| 有效 batch 不够但显存满 | 降 micro-batch + 升 grad_accum |

**硬提醒**：(1) `use_reentrant=False` 几乎是 LoRA+GC 必需；(2) QLoRA 必须 `prepare_model_for_kbit_training` 在前、`bnb_4bit_compute_dtype=bf16`；(3) FSDP 下用 `activation_checkpointing` 而非 HF GC，勿叠；(4) Liger 的 CE 与 FLCE 互斥；(5) packing+bfd 自动开 padding-free，padding_free 仅限 FlashAttention。

**Sources**：[FSDP2 fully_shard](https://docs.pytorch.org/docs/2.9/distributed.fsdp.fully_shard.html) · [accelerate FSDP vs DeepSpeed](https://huggingface.co/docs/accelerate/en/concept_guides/fsdp_and_deepspeed) · [DeepSpeed ZeRO](https://www.deepspeed.ai/tutorials/zero/) · [bitsandbytes optimizers](https://huggingface.co/docs/bitsandbytes/main/en/optimizers) · [transformers bitsandbytes](https://huggingface.co/docs/transformers/main/en/quantization/bitsandbytes) · [PEFT LoRA](https://huggingface.co/docs/peft/main/en/developer_guides/lora) · [TRL SFTConfig](https://github.com/huggingface/trl/blob/main/trl/trainer/sft_config.py) · [Liger-Kernel](https://github.com/linkedin/Liger-Kernel) · [Unsloth long-context](https://unsloth.ai/blog/long-context)
