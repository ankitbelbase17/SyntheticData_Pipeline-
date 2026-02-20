#!/bin/bash --login
#SBATCH --account a168
#SBATCH --partition normal
#SBATCH --time 4:00:00
#SBATCH --output /capstor/store/cscs/swissai/a168/dbartaula/logs/%A_edit.log
#SBATCH --error  /capstor/store/cscs/swissai/a168/dbartaula/logs/%A_edit.err
#SBATCH --nodes 4                  # 4 nodes × 4 GPUs = 16 GPUs total
#SBATCH --ntasks-per-node=4
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=8
#SBATCH --mem 400G

# ── Environment ──────────────────────────────────────────────
export HF_HOME=/iopsstor/scratch/cscs/dbartaula/.cache/huggingface
export PYTHONUNBUFFERED=1
export NCCL_IB_DISABLE=0

# ── Distributed setup ────────────────────────────────────────
export MASTER_ADDR=$(scontrol show hostnames "$SLURM_NODELIST" | head -n 1)
export MASTER_PORT=29501            # different port to avoid clash with beans job
export WORLD_SIZE=16

JOB_START=$(date '+%Y-%m-%d %H:%M:%S')

echo "============================================================"
echo "Job ID    : $SLURM_JOB_ID"
echo "Nodes     : $(scontrol show hostnames "$SLURM_NODELIST" | tr '\n' ' ')"
echo "MASTER    : $MASTER_ADDR:$MASTER_PORT"
echo "WORLD_SIZE: $WORLD_SIZE"
echo "START TIME: $JOB_START"
echo "============================================================"

mkdir -p /capstor/store/cscs/swissai/a168/dbartaula/logs
mkdir -p /iopsstor/scratch/cscs/dbartaula/edit_prompts

SCRIPT_DIR="/capstor/store/cscs/swissai/a168/dbartaula"

# ── Pre-flight check ─────────────────────────────────────────
echo "--- Pre-flight ---"
python - <<'EOF'
import sys, os
try:
    import torch
    print(f"torch: {torch.__version__} | GPUs: {torch.cuda.device_count()}")
except Exception as e:
    print(f"FAIL torch: {e}"); sys.exit(1)
try:
    import flash_attn
    print(f"flash_attn: {flash_attn.__version__}")
except Exception as e:
    print(f"FAIL flash_attn: {e}"); sys.exit(1)
try:
    from transformers import AutoProcessor
    print("transformers: OK")
except Exception as e:
    print(f"FAIL transformers: {e}"); sys.exit(1)
from PIL import Image
for img in ["female.png", "male.png"]:
    p = f"/capstor/store/cscs/swissai/a168/dbartaula/{img}"
    if os.path.exists(p):
        print(f"  Image {img}: OK ({os.path.getsize(p)//1024}KB)")
    else:
        print(f"  MISSING: {p}"); sys.exit(1)
import py_compile
try:
    py_compile.compile(f"/capstor/store/cscs/swissai/a168/dbartaula/qwen_edit_prompts.py", doraise=True)
    print("qwen_edit_prompts.py syntax: OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}"); sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "Pre-flight FAILED."
    exit 1
fi
echo "--- Pre-flight passed ---"

# ── Launch 16 parallel GPU workers ───────────────────────────
srun -u \
    --environment=qwen3vl-fa2 \
    bash -c "
        export RANK=\$SLURM_PROCID
        export LOCAL_RANK=\$SLURM_LOCALID
        echo \"[RANK \$RANK | GPU \$LOCAL_RANK] on \$(hostname)\"

        python /capstor/store/cscs/swissai/a168/dbartaula/qwen_edit_prompts.py \
            --json_dir   /capstor/store/cscs/swissai/a168/dbartaula \
            --image_dir  /capstor/store/cscs/swissai/a168/dbartaula \
            --output_dir /iopsstor/scratch/cscs/dbartaula/edit_prompts \
            --max_samples    3000 \
            --batch_size     48 \
            --max_new_tokens 256 \
            --model_name     'Qwen/Qwen3-VL-32B-Instruct'
    "

EXIT_CODE=$?
JOB_END=$(date '+%Y-%m-%d %H:%M:%S')
START_EPOCH=$(date -d "$JOB_START" +%s)
END_EPOCH=$(date -d "$JOB_END" +%s)
ELAPSED=$((END_EPOCH - START_EPOCH))

echo "============================================================"
echo "START TIME : $JOB_START"
echo "END TIME   : $JOB_END"
echo "Wall time  : ${ELAPSED}s ($(( ELAPSED/60 ))m $(( ELAPSED%60 ))s)"
echo "Exit code  : $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "STATUS     : SUCCESS"
    TXT_COUNT=$(ls /iopsstor/scratch/cscs/dbartaula/edit_prompts/*.txt 2>/dev/null | wc -l)
    echo "TXT files  : $TXT_COUNT"
    echo "JSONL files:"
    ls -lh /iopsstor/scratch/cscs/dbartaula/edit_prompts/edit_prompts_rank*.jsonl 2>/dev/null
else
    echo "STATUS     : FAILED — check logs"
fi
echo "============================================================"
