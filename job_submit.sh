#!/bin/bash --login
#SBATCH --account a168
#SBATCH --partition normal
#SBATCH --time 4:00:00
#SBATCH --output /capstor/store/cscs/swissai/a168/dbartaula/logs/%A.log
#SBATCH --error  /capstor/store/cscs/swissai/a168/dbartaula/logs/%A.err
#SBATCH --nodes 4                 # 4 nodes
#SBATCH --ntasks-per-node=4       # 4 tasks per node = 16 total GPU workers
#SBATCH --gpus-per-task=1         # 1 GPU per task
#SBATCH --cpus-per-task=8
#SBATCH --mem 400G

# ── HuggingFace cache ─────────────────────────────────────────
export HF_HOME=/iopsstor/scratch/cscs/dbartaula/.cache/huggingface
export PYTHONUNBUFFERED=1
export NCCL_IB_DISABLE=0          # keep InfiniBand for cross-node NCCL

# ── Master node = first node in SLURM allocation ──────────────
# Must be reachable by all 8 tasks across both nodes
export MASTER_ADDR=$(scontrol show hostnames "$SLURM_NODELIST" | head -n 1)
export MASTER_PORT=29500
export WORLD_SIZE=16              # 4 nodes × 4 GPUs

# ── Timestamps ────────────────────────────────────────────────
JOB_START=$(date '+%Y-%m-%d %H:%M:%S')

echo "============================================================"
echo "Job ID    : $SLURM_JOB_ID"
echo "Nodes     : $(scontrol show hostnames "$SLURM_NODELIST" | tr '\n' ' ')"
echo "MASTER    : $MASTER_ADDR:$MASTER_PORT"
echo "WORLD_SIZE: $WORLD_SIZE"
echo "START TIME: $JOB_START"
echo "WorkDir   : /capstor/store/cscs/swissai/a168/dbartaula"
echo "============================================================"

mkdir -p /capstor/store/cscs/swissai/a168/dbartaula/logs

# ── Launch 8 parallel GPU workers across 2 nodes ──────────────
# srun distributes 4 tasks to node-0 and 4 tasks to node-1.
# Each task gets its own GPU (remapped to cuda:0 via CUDA_VISIBLE_DEVICES).
# NCCL uses InfiniBand for cross-node communication.
srun -u \
    --environment=qwen3vl-fa2 \
    bash -c "
        export RANK=\$SLURM_PROCID
        export LOCAL_RANK=\$SLURM_LOCALID

        echo \"[RANK \$RANK / LOCAL_RANK \$LOCAL_RANK] on \$(hostname) | GPU: \$CUDA_VISIBLE_DEVICES\"

        cd /capstor/store/cscs/swissai/a168/dbartaula
        python qwen_hf_beans.py \
            --batch_size     64 \
            --max_new_tokens 512 \
            --max_samples    960 \
            --model_name     'Qwen/Qwen3-VL-32B-Instruct' \
            --output_dir     /capstor/store/cscs/swissai/a168/dbartaula
    "

EXIT_CODE=$?
JOB_END=$(date '+%Y-%m-%d %H:%M:%S')

echo "============================================================"
echo "START TIME : $JOB_START"
echo "END TIME   : $JOB_END"
echo "Exit code  : $EXIT_CODE"

# Compute total wall time in seconds
START_EPOCH=$(date -d "$JOB_START" +%s)
END_EPOCH=$(date -d "$JOB_END" +%s)
ELAPSED=$((END_EPOCH - START_EPOCH))
echo "Wall time  : ${ELAPSED}s ($(( ELAPSED/60 ))m $(( ELAPSED%60 ))s)"

if [ $EXIT_CODE -eq 0 ]; then
    echo "STATUS     : SUCCESS"
    echo "Output files:"
    ls -lh /capstor/store/cscs/swissai/a168/dbartaula/beans_predictions_rank*.jsonl 2>/dev/null
    TOTAL=$(cat /capstor/store/cscs/swissai/a168/dbartaula/beans_predictions_rank*.jsonl 2>/dev/null | wc -l)
    echo "Total records: $TOTAL"
else
    echo "STATUS     : FAILED — check logs"
fi
echo "============================================================"