#!/usr/bin/env bash
# bin/remote_exec.sh — 把一个实验 segment 送到远程 Slurm 集群跑，本地【前台阻塞】直到它结束。
#
#   remote_exec.sh <segment-id> <远程工作目录> <要跑的命令> [产物相对路径,逗号分隔]
#
# 为什么必须前台阻塞：exp_ledger.py run-detach 把这条命令 Popen 到后台并记录 PID，asyncRewake 的
# Stop hook OS-wait 那个 PID。本脚本活着 == 远程作业在跑 == L0 零 token 等待。所以这里绝不能自己
# nohup/& 甩到后台，否则 L0 会以为实验秒完就去写 result.md。Slurm 排队时间同样被这段阻塞覆盖，
# 排队不计费也不烧 token —— 不要为了躲排队而缩小实验。
#
# 环境变量（都有默认值，改 key-config 或 export 均可）：
#   AR_REMOTE_HOST      ssh 别名，默认 slurm-cluster
#   AR_SLURM_PARTITION  分区，默认 gpu（GPU）；CPU 用 dzacnormal
#   AR_SLURM_GRES       默认 gpu:1；设成 none 则不申请 GPU
#   AR_SLURM_TIME/CPUS  墙钟上限 / 每任务核数，默认 08:00:00 / 8
#   AR_CONDA_ENV        远程 conda 环境，默认 base
#   AR_POLL_SECONDS     轮询间隔，默认 60（走 ControlMaster 复用连接，开销可忽略）
#   AR_LOCAL_DIR        要推上去的本地目录，默认 $PWD
#
# 踩过的坑（改动前先读）：
#   · 脚本内每个 ssh 都必须带 -n。不带会吞掉 stdin，整个脚本静默卡死。
#     反过来：需要用 heredoc 往远程送脚本时不能带 -n（-n 把 stdin 指向 /dev/null）。
#   · rsync 推代码禁用 --delete/--delete-excluded，否则会删掉远程已产出的 results/。
set -euo pipefail

usage() { sed -n '2,6p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2; }
[ $# -ge 3 ] || usage
SEG="$1"; REMOTE_DIR="$2"; CMD="$3"; PRODUCTS="${4:-}"

HOST="${AR_REMOTE_HOST:-slurm-cluster}"
PART="${AR_SLURM_PARTITION:-gpu}"
GRES="${AR_SLURM_GRES:-gpu:1}"
TLIMIT="${AR_SLURM_TIME:-08:00:00}"
CPUS="${AR_SLURM_CPUS:-8}"
CENV="${AR_CONDA_ENV:-base}"
POLL="${AR_POLL_SECONDS:-60}"
LOCAL_DIR="${AR_LOCAL_DIR:-$PWD}"
if [ "$GRES" = "none" ] || [ -z "$GRES" ]; then GRES_LINE=""; else GRES_LINE="#SBATCH --gres=$GRES"; fi

# ① 推代码（不带 --delete：远程 results/ logs/ 是产物，删了就没了）
rsync -az \
  --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' --exclude '.venv' \
  --exclude 'results/' --exclude 'logs/' \
  "$LOCAL_DIR/" "$HOST:$REMOTE_DIR/"

# ② 生成 sbatch 脚本并提交（heredoc 送脚本，故意不加 -n）
JID=$(ssh -o BatchMode=yes "$HOST" "mkdir -p '$REMOTE_DIR/logs' && cat > '$REMOTE_DIR/logs/$SEG.slurm' <<'SLURM'
#!/bin/bash
#SBATCH -J ar_$SEG
#SBATCH -p $PART
$GRES_LINE
#SBATCH -N 1 -n 1 --cpus-per-task=$CPUS
#SBATCH -t $TLIMIT
#SBATCH -o $REMOTE_DIR/logs/$SEG.out
set -u
source ~/miniconda3/etc/profile.d/conda.sh
conda activate $CENV
cd $REMOTE_DIR
echo \"AR_SEG=$SEG HOST=\$(hostname) START=\$(date -Is)\"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'no GPU on this node'
$CMD
rc=\$?
echo \"AR_EXIT=\$rc END=\$(date -Is)\"
exit \$rc
SLURM
sbatch --parsable '$REMOTE_DIR/logs/$SEG.slurm'")
echo "[remote_exec] segment=$SEG jobid=$JID host=$HOST partition=$PART gres=$GRES" >&2

# ③ 前台阻塞等待 —— 这正是 L0 要 OS-wait 的那段时间（含排队）
while ssh -n -o BatchMode=yes "$HOST" "squeue -j $JID -h -o %T 2>/dev/null | grep -q ."; do sleep "$POLL"; done

# ④ 拉回产物；再把远程 stdout 回放到本地 stdout（run-detach 捕获它并算 SHA）
if [ -n "$PRODUCTS" ]; then
  IFS=',' read -ra PS <<< "$PRODUCTS"
  for p in "${PS[@]}"; do
    mkdir -p "$LOCAL_DIR/$(dirname "$p")"
    rsync -az "$HOST:$REMOTE_DIR/$p" "$LOCAL_DIR/$p" || echo "[remote_exec] WARN 产物缺失: $p" >&2
  done
fi
ssh -n "$HOST" "cat '$REMOTE_DIR/logs/$SEG.out'"
RC=$(ssh -n "$HOST" "sacct -j $JID -n -o ExitCode 2>/dev/null | head -1 | cut -d: -f1 | tr -d ' '")
echo "[remote_exec] segment=$SEG slurm_exit=${RC:-unknown}" >&2
exit "${RC:-1}"
