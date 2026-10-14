# Reference — 科学计算（非深度学习）GPU 加速

> 由 `experiment-engineering/SKILL.md` 在实验是数值线代/蒙特卡洛/分子模拟/PDE/大数组计算（而非神经网络训练）时按需 Read。
> 版本核实：2026-06。

**选库第一原则：先看改多少代码。** 三档心智模型——
- **(A) 几乎零改**（换 import 或加一行）：`cudf.pandas` / `cuml.accel` / cuPyNumeric
- **(B) 浅改**（换命名空间 + 显式管 device 数组）：CuPy、PyTorch-as-array
- **(C) 需重写成函数式或 kernel**：JAX、Numba CUDA、Triton、Warp

**第二原则：float64。** 物理/数值默认要双精度，而消费级 GeForce（RTX 40/50）的 FP64 吞吐是 FP32 的 **1/32 到 1/64**（硬件阉割）；数据中心卡（A100/H100/H200/B200）FP64 才是 FP32 的 1/2。这比选哪个库更关键——下面每条都标 float64 行为。

---

## 1. CuPy — NumPy/SciPy 的 drop-in GPU 替换

**版本：稳定 13.6.0，按 CUDA 主版本选 wheel：`pip install cupy-cuda12x` 或 `cupy-cuda13x`。** 实现 NumPy 绝大部分 + `cupyx.scipy`（FFT/`ndimage`/`signal`/`linalg`/稀疏 CSR/CSC + `spsolve`/CG/GMRES）。

① **适用**：已有 NumPy/SciPy 风格稠密/稀疏数组计算——线代（`cp.linalg.svd/eigh/solve`，cuSOLVER）、FFT（cuFFT）、大 elementwise/reduction、蒙特卡洛（`cupy.random`，cuRAND）、稀疏迭代解 PDE。**最甜区**：单个大数组，N ≳ 10^6，算术强度中到高。
② **drop-in：B 档（最高的"伪 drop-in"）**。`import cupy as cp`（很多代码 `import cupy as np` 直接顶替），API 同名同签。但必须显式管 device 数组、用 `cp.asarray`/`.get()` 过边界。
③ **片段**：
```python
import cupy as cp
x = cp.random.rand(10_000, 10_000)        # 直接 GPU 上生成，不过边界
y = cp.linalg.svd(x, compute_uv=False)    # cuSOLVER
result = float(y[0].get())                # 仅把需要的标量取回 host
```
④ **加速比**：稠密大矩阵/FFT/高算术强度 elementwise，**vs NumPy(CPU) 10–100×**（厂商演示到 150–200×，多见 float32 + 超大 N）。**这是上界**——小数组或低算术强度常常不快甚至更慢。
⑤ **不值**：数组小（N < 10^4~10^5）；大量 Python 标量循环穿插小 GPU 调用（每次 launch 5–50µs 延迟吞掉收益）；频繁 host↔device 往返。
⑥ **坑**：
- **拷贝开销是头号杀手**。`cp.asarray`(H2D)/`.get()`(D2H) 走 PCIe，带宽远低于显存。策略：**数据尽早上 GPU、全程留 GPU、只把最终标量 `.get()` 回来**；频繁传用 pinned memory（`cupyx.empty_pinned`）。
- **float64**：完整支持但速度受硬件 FP64 比率支配（消费卡可能慢 32–64×）。默认 float32，确需双精度再上。
- **首次 kernel 编译**：RawKernel/ElementwiseKernel/`fuse` 首调要 NVRTC 编译（亚秒级），基准测试要 **warm-up 一次再计时**，并 `cp.cuda.Stream.null.synchronize()`（GPU 异步，不同步会量到假的"超快"）。

**写自定义 kernel（仍在 CuPy 内）**——内置 ufunc 组合不够、或想把多步融合省显存带宽：
```python
sq_diff = cp.ElementwiseKernel('T x, T y', 'T z', 'z = (x-y)*(x-y)', 'sq_diff')
l2 = cp.ReductionKernel('T x', 'T y', 'x*x', 'a+b', 'y=sqrt(a)', '0', 'l2norm')
add = cp.RawKernel(r'''
extern "C" __global__ void my_add(const float* a, const float* b, float* y){
    int i = blockDim.x*blockIdx.x + threadIdx.x;  y[i] = a[i]+b[i];
}''', 'my_add')
add((blocks,), (threads,), (a, b, y))
@cp.fuse()
def f(x, y): return (x - y) * (x - y)   # 最省事：自动融合成单 kernel
```
取舍：**`@cp.fuse` > Elementwise/ReductionKernel > RawKernel**，按"省事"递减、"控制力"递增。融合多个 elementwise 步骤成一个 kernel 显著减少显存读写往返（科学计算常 memory-bound，这是主要收益）。RawKernel 仅当需 shared memory/warp 原语/复杂索引/粘贴现成 `.cu`。

---

## 2. JAX — `jit` + `vmap` + `grad` + XLA 融合

**版本：0.10.x。安装带 CUDA：`pip install -U "jax[cuda12]"`。** NumPy 风格（`jax.numpy as jnp`）+ 可组合变换（`jit`/`grad`/`vmap`/`scan`）+ XLA 算子融合。

① **适用**：需**自动微分**的科学计算（梯度优化、灵敏度分析、参数反演、可微仿真、PINN、变分法）；大量同构小问题批处理（`vmap`）。生态：JAX-MD、Diffrax（ODE/SDE）、Optimistix、Lineax、BlackJAX。
② **drop-in：C 档（需重写成函数式纯函数）**。最大门槛：被变换函数必须**无副作用**（`x.at[i].set(v)` 而非 `x[i]=v`；随机数显式传 `key`）。控制流用 `jax.lax.scan`/`cond`/`while_loop` 而非 Python 循环（Python 循环被展开 → 编译爆炸/反复 retrace）。
③ **片段**：
```python
import jax, jax.numpy as jnp
jax.config.update("jax_enable_x64", True)         # 必须最早处，否则静默降 float32
def potential(x): return jnp.sum(jnp.sin(x)**2)
force = jax.jit(jax.grad(potential))              # 自动微分 + 编译
batched = jax.jit(jax.vmap(force))                # 一次对一批求力，零循环
F = batched(jnp.ones((4096, 3)))
```
④ **加速比**：同量级（10–100× vs CPU）。**JAX 碾压 PyTorch 的场景**：(a) `jit(vmap(grad(f)))` 把"求值+求梯度+批处理"融合成极少数大 kernel；(b) 大量小独立问题 `vmap` 向量化。**反向校准**：JAX-MD 大体系比 LAMMPS/HOOMD 慢（GPU ~2.4× 慢），XLA 为 ML 调、缺生产级 MD kernel。**JAX 杀手锏是"可微+自动批处理+融合"，不是"无脑比谁都快"**。
⑤ **不值**：纯前向无梯度、已有成熟 CUDA 库（CuPy 更省事）；代码满是就地修改/Python 控制流不愿重写；问题小到编译开销摊不平。
⑥ **坑**：
- **64-bit 默认关闭**——不设 `jax_enable_x64=True`，所有 float64 静默截断到 float32（数值方法灾难）。必须程序最开头设。
- **首次编译 + recompile**：每遇新 shape/dtype 重编译，变长循环喂不同 shape 会反复 retrace。对策：固定 shape、`lax.scan` 取代 Python 循环、`static_argnums` 标编译期常量。计时跳首次 + `.block_until_ready()`。
- **`donate_argnums`**：原地复用输入 buffer 当输出省显存（时间步进迭代关键）：`jax.jit(step, donate_argnums=(0,))`。被捐参数调用后不可再用。
- **`pmap` 进入维护模式**：多设备并行新代码用 `jax.shard_map` + `jax.sharding`。
- **随机数**：无全局 RNG，必须 `key, sub = jax.random.split(key)`，否则同 key 给相同"随机"序列（蒙特卡洛隐蔽 bug）。

---

## 3. Numba CUDA — `@cuda.jit` 手写 kernel

**版本/重要变更：Numba 0.61 起内置 `numba.cuda` 后端弃用，迁到独立包 `numba-cuda`（NVIDIA 维护）。装：`pip install numba-cuda`，命名空间仍是 `numba.cuda`。**

① **适用**：算法**不能表达成数组运算**、需逐线程逻辑/shared memory/原子——粒子近邻、stencil/有限差分、直方图、自定义蒙特卡洛更新、cellular automata。
② **drop-in：C 档（写 kernel）**，但用 Python 子集写，不碰 CUDA C。
③ **片段**：
```python
from numba import cuda
@cuda.jit
def axpy(a, x, y, out):
    i = cuda.grid(1)                 # = blockIdx.x*blockDim.x + threadIdx.x
    if i < x.size:                   # 边界检查必写
        out[i] = a*x[i] + y[i]
threads = 256; blocks = (x.size + threads - 1)//threads
axpy[blocks, threads](2.0, x, y, out)   # 方括号 = 配 grid/block
```
线程模型：`cuda.grid(1/2)`；`cuda.shared.array(shape, dtype)`；`cuda.syncthreads()`；`cuda.atomic.add`。
④ **加速比**：手写 kernel 对 memory-bound stencil/直方图，vs NumPy 10–数百×（同 CuPy RawKernel——两者最终都是一个 CUDA kernel）。
⑤ **何时值得**：内置 ufunc 拼不出、需 shared memory 数据复用、要原子归约。**不值**：能用 `cp.ElementwiseKernel`/`@cp.fuse`/JAX 表达的别手写（调试成本高、易 race/越界）。
⑥ **vs CuPy RawKernel**：Numba 纯 Python 写、调试友好（`NUMBA_ENABLE_CUDASIM=1` CPU 模拟）；RawKernel 写 CUDA C、可复用现成 `.cu`、用最新 CUDA 特性。**纯 Python 团队→Numba；有 CUDA C/要 warp 原语→RawKernel**。两库经 `__cuda_array_interface__` 零拷贝互操作，可混用。

---

## 4. Triton（triton-lang）— 用 Python 写融合 kernel

**版本：3.7.0；随 PyTorch 绑定（`pip install torch` 自带）。** Python DSL，写**块级（tile）**程序，编译器自动处理 thread 调度/合并访存/shared memory/向量化。

① **适用**：写**融合算子**——多步 elementwise + reduction 融成一个 kernel（融合 softmax/layernorm/自定义激活/fused attention/带权归约/量化 matmul 变体）。科学计算：把"一串逐元素变换 + 一个 reduction"融成单 kernel 省带宽。
② **drop-in：C 档**，但比 CUDA C 易一个数量级——`tl.load`/`tl.store` + 掩码 + `tl.sum` 等块级原语。
③ **片段**：
```python
import triton, triton.language as tl
@triton.jit
def add_kernel(x_ptr, y_ptr, out_ptr, n, BLOCK: tl.constexpr):
    pid = tl.program_id(0); off = pid*BLOCK + tl.arange(0, BLOCK); m = off < n
    tl.store(out_ptr+off, tl.load(x_ptr+off, mask=m) + tl.load(y_ptr+off, mask=m), mask=m)
add_kernel[(triton.cdiv(n, 1024),)](x, y, out, n, BLOCK=1024)
```
④ **加速比**：相对 PyTorch eager 逐算子，融合 kernel 常 **2–10×**（省 launch 数 + 显存往返）；对手写 CUDA C 多数打平或接近（80–100%），换开发量大减。**卖点是"vs PyTorch 未融合"和"vs 手写 CUDA 开发成本"，不是碾压 cuBLAS/cuDNN**。
⑤ **何时用**：标准库没有的融合算子。**不值**：能用 cuBLAS/cuFFT/cuSOLVER 的标准操作；纯数组运算用 CuPy/JAX 更省事；float64 重数值（Triton 生态以 fp16/bf16/fp32 为主，float64 支持远不如低精度成熟）。
⑥ **与 `torch.compile`**：`torch.compile` 后端（TorchInductor）默认就把融合算子下降为 Triton kernel——PyTorch 2.x 的"自动融合"产物就是 Triton。多数人**间接**用 Triton；只有自动融合不够好才**直接**写。坑：autotune 首次很慢；最优 `BLOCK`/`num_warps` 随架构变；float64 路径少人走。

---

## 5. RAPIDS — cuDF / cuML / cuGraph / cuPyNumeric

**版本：CalVer，stable 已到 25.x（cuML 25.10 起可 `pip install` from PyPI）。** "几乎零改"档主力。

**cuDF（GPU DataFrame）**：pandas 风格清洗/聚合/join/groupby。**drop-in：A 档，零改**——`%load_ext cudf.pandas` 或 `python -m cudf.pandas your.py`，不支持的算子自动回退 CPU。加速 **vs pandas 数十×，演示到 ~150×**。不值：小表（<~10^5 行）；逻辑全是逐行 `apply`。坑：装不下整表 OOM（25.x 有 UVM/spilling 缓解）。

**cuML（GPU 经典 ML）**：**非深度学习的经典 ML**——KNN、PCA/TruncatedSVD、KMeans/DBSCAN/HDBSCAN、UMAP、随机森林、线性/逻辑/岭回归、SVM。正中物理/材料的"描述符 + 经典 ML"。**drop-in：A 档**——`python -m cuml.accel your_sklearn.py` 或 `%load_ext cuml.accel`，**不改 sklearn 代码**，支持的 GPU 跑、不支持回退。加速 **vs sklearn ~50×**。坑：数值结果与 sklearn 可能微小差异；float64 支持因算法而异，部分内部偏好 float32。

**cuGraph（GPU 图算法）**：PageRank/BFS/SSSP/连通分量/社区发现/中心性。drop-in：NetworkX 后端零改（`NX_CUGRAPH_AUTOCONFIG=True`）。大图 vs NetworkX 数十到数百×。

**cuPyNumeric（前身 cuNumeric）**：**把单机 NumPy 程序无改动跨多 GPU/多节点 scale**。**drop-in：A 档，独一份的"多卡零改"**——`import cupynumeric as np` 顶替 `import numpy as np`，单 CPU 扩到多节点多 GPU 无需改（演示 2048×A100 跑同一份 CFD）。底层 Legate/Legion。收益来自**分布式扩展**非单核常数倍。不值：塞得进单卡（CuPy 更轻、生态更全）。坑：需 Legate 运行时 + 多卡/集群部署；API 覆盖不及 CuPy 全。**CuPy（单 GPU）和 cuPyNumeric（多 GPU/多节点）是两个不同项目，别混。**

---

## 6. 物理仿真专用 — NVIDIA Warp / Taichi

**Warp（`warp-lang`）：稳定 1.10–1.13；`pip install warp-lang`，NVIDIA 维护、活跃。**
① 适用：**可微 GPU 仿真**——粒子、MPM、SPH、FEM、布料/软体、机器人、连续介质；尤其要把仿真**接进 ML 管线求梯度**（系统辨识、可微设计、sim-to-real）。
② drop-in：C 档，写 `@wp.kernel`（Python 子集），kernel **自动可微**。
```python
import warp as wp
@wp.kernel
def integrate(x: wp.array(dtype=wp.vec3), v: wp.array(dtype=wp.vec3), dt: float):
    i = wp.tid(); x[i] = x[i] + v[i]*dt
wp.launch(integrate, dim=len(x), inputs=[x, v, 0.01])
```
④ 加速：编译成 CUDA，vs 纯 Python 粒子循环数十到数百×。⑤ **何时用**：要可微物理、或与 PyTorch/JAX 零拷贝互操作、或写自定义仿真 kernel。**不值**：只要成熟前向 MD/CFD（用 LAMMPS/GROMACS/OpenFOAM）——Warp 不是完整物理引擎。⑥ 坑：Python 子集受限（比 Numba 还窄）；可微要正确标注、内存随反向图涨；float64 有限。

**Taichi（`taichi`）：1.7.4，但项目已进入维护/修 bug 模式、几乎停止活跃开发。**
① 适用：稀疏/不规则空间数据结构（SNode）、stencil、MPM/流体、可微（DiffTaichi）；后端跨 CUDA/Vulkan/Metal/CPU（**唯一对 Apple Metal 友好**）。② drop-in：C 档，`@ti.kernel`。⑤ **何时用**：需跨平台后端（尤其 Mac/Metal）、或维护已有 Taichi 代码。**新项目若需长期维护与新特性，优先 Warp**（Taichi 活跃开发已基本停滞）。⑥ 坑：维护状态意味新硬件/CUDA/Python 支持滞后。

---

## 7. PyTorch 当通用 GPU 数组 + autograd 库（不建网络）

**版本：PyTorch 2.x，`torch.func` 已稳定（前身 functorch 并入核心）。** 把 PyTorch 仅当"带 autograd 的 GPU NumPy"——`torch.Tensor` 做数组、`device='cuda'` 上卡、`torch.func` 求导，完全不碰 `nn.Module`。

① 适用：要 GPU 数组 + 反向传播梯度，但想要 PyTorch 的成熟生态/调试/eager 灵活。优化、参数拟合、需要 Jacobian/Hessian 的数值方法。**与 JAX 取舍**：要逐步调试/动态控制流/已有 PyTorch 技能栈 → PyTorch；要极致融合 + `vmap` 海量小问题 + 纯函数式 → JAX。
② drop-in：B 档，`np.`→`torch.`（多同名，少数不同如 `axis`→`dim`、`concatenate`→`cat`）+ 显式 device。
③ **片段（含 `torch.func`，JAX 式可组合变换）**：
```python
import torch
from torch.func import grad, vmap, jacrev, hessian
torch.set_default_dtype(torch.float64)          # 科学计算开双精度
def f(x): return (x.sin()**2).sum()
g  = grad(f)                                     # 梯度（函数式，无需 .backward()）
H  = hessian(f)                                  # 便捷 = jacfwd∘jacrev
batched_grad = vmap(grad(f))                     # 对一批输入并行求梯度
x = torch.randn(4096, 3, device='cuda')
out = batched_grad(x)                            # GPU 上一次算完
```
`torch.func` 提供 `grad/vjp/jvp/jacrev/jacfwd/hessian/vmap`——PyTorch 里对标 JAX 变换的部分，可组合算批量 Jacobian/Hessian（科学计算要的灵敏度/曲率）。
⑥ 坑：float64 支持好但默认 float32，忘设静默单精度；拷贝开销同 CuPy（数据留 GPU 少往返）；`torch.func` 要求函数式风格；GPU 异步基准要 `torch.cuda.synchronize()` + warm-up 跳首次；Torch CUDA tensor ↔ CuPy 经 DLPack 零拷贝（`cp.from_dlpack(t)` / `torch.from_dlpack(c)`）。

---

## 选型速查

| 需求 | 首选 | 改代码量 |
|---|---|---|
| 已有 NumPy/SciPy 稠密/稀疏/FFT/线代，单 GPU | **CuPy** | 浅 |
| 同上但扩到多卡/多节点、零改 | **cuPyNumeric** | 几乎零 |
| pandas 数据处理 | **cuDF**（`cudf.pandas`） | 零 |
| 经典 ML（KNN/PCA/聚类/RF/回归/UMAP） | **cuML**（`cuml.accel`） | 零 |
| 自动微分 + 批处理 + 整图融合，能写纯函数 | **JAX** | 重 |
| autograd + GPU，偏好 PyTorch 工效 | **PyTorch + `torch.func`** | 浅—中 |
| 手写 kernel、纯 Python 团队 | **Numba `@cuda.jit`**（装 `numba-cuda`） | 重 |
| 手写 kernel、复用 CUDA C / warp 原语 | **CuPy RawKernel** | 重 |
| 写融合算子、不碰 CUDA C | **Triton**（多数时候让 `torch.compile` 自动生成） | 重 |
| 可微物理仿真（粒子/MPM/FEM）+ ML 集成 | **NVIDIA Warp** | 重 |
| 跨平台仿真（含 Apple Metal）/ 维护旧码 | **Taichi**（注意半停更） | 重 |

**三条铁律**：(1) **host↔device 拷贝是最常见的"GPU 反而更慢"根因**——数据尽早上卡、全程留卡、只取回小结果（各库间可 DLPack 零拷贝换手）。(2) **float64 在消费级 GPU 上可能慢 32–64×**——先确认你的卡是数据中心卡（FP64=½FP32）还是 GeForce（被阉割），再决定算法值不值上 GPU；JAX 还要显式 `jax_enable_x64=True`。(3) **JIT 首次编译 + GPU 异步**——基准必须 warm-up 跳首次 + 显式 `synchronize()`/`block_until_ready()`，否则量到的"超快"是假的。

**Sources**：[CuPy](https://cupy.dev/) · [CuPy 自定义 kernel](https://docs.cupy.dev/en/stable/user_guide/kernel.html) · [JAX Sharp Bits](https://docs.jax.dev/en/latest/notebooks/Common_Gotchas_in_JAX.html) · [JAX X64](https://docs.jax.dev/en/latest/default_dtypes.html) · [numba-cuda](https://nvidia.github.io/numba-cuda/) · [Triton](https://github.com/triton-lang/triton) · [cuML zero-code-change](https://developer.nvidia.com/blog/nvidia-cuml-brings-zero-code-change-acceleration-to-scikit-learn/) · [cuDF 150× pandas](https://developer.nvidia.com/blog/rapids-cudf-accelerates-pandas-nearly-150x-with-zero-code-changes) · [Warp](https://nvidia.github.io/warp/) · [torch.func Jacobians/Hessians](https://docs.pytorch.org/tutorials/intermediate/jacobians_hessians.html) · [JAX-MD 论文](https://arxiv.org/pdf/1912.04232)
